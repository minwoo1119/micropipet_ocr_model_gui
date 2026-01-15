import subprocess
import json
import time
import os
import sys
import random
import cv2

from worker.capture_frame import OUTPUT_PATH
from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator

# ==========================================================
# Config
# ==========================================================
SNAP_DIR = "snapshots"

BATCH_COUNT = 1000
TARGET_MIN = 500
TARGET_MAX = 5000

VOLUME_TOLERANCE = 1
SETTLE_TIME = 0.7
MAX_ITER = 60
OCR_TIMEOUT = 20
INTER_RUN_DELAY_SEC = 1.0

# OCR sanity
VALID_MIN_UL = 500
VALID_MAX_UL = 5000
JUMP_THRESHOLD_UL = 200
MAX_OCR_RETRY = 2

# OCR stuck
MAX_SAME_OCR_COUNT = 5

# Direction check
MAX_DIR_MISMATCH_RETRY = 2

# Nudge
NUDGE_DUTY = 25
NUDGE_DURATION_MS = 70
NUDGE_DIRECTION = 1
NUDGE_SETTLE_SEC = 0.15

ROTATE = 1  # 90 CW

# ==========================================================
# Global actuator
# ==========================================================
_serial = None
_volume_dc = None


def ensure_dirs():
    os.makedirs(SNAP_DIR, exist_ok=True)


def ensure_volume_dc():
    global _serial, _volume_dc

    if _serial is None:
        _serial = SerialController()
        _serial.connect()

    if _volume_dc is None:
        _volume_dc = VolumeDCActuator(
            serial=_serial,
            actuator_id=0x0C,
        )

    return _volume_dc


# ==========================================================
# Snapshot utils
# ==========================================================
def get_next_snapshot_index():
    if not os.path.exists(SNAP_DIR):
        return 1

    max_idx = 0
    for f in os.listdir(SNAP_DIR):
        if f.endswith(".jpg"):
            try:
                max_idx = max(max_idx, int(f.split("_")[0]))
            except Exception:
                pass
    return max_idx + 1


def save_snapshot(order: int, target_ul: int):
    fname = f"{order:04d}_{target_ul:04d}.jpg"
    dst = os.path.join(SNAP_DIR, fname)

    img = cv2.imread(OUTPUT_PATH)
    if img is None:
        raise RuntimeError("last_frame.jpg not found")

    if ROTATE == 1:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif ROTATE == 2:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif ROTATE == 3:
        img = cv2.rotate(img, cv2.ROTATE_180)

    cv2.imwrite(dst, img)
    print(f"[SNAPSHOT] saved → {dst}")


# ==========================================================
# OCR
# ==========================================================
def read_ocr():
    cmd = [
        sys.executable, "-m", "worker.worker",
        "--ocr",
        "--camera=0",
        f"--rotate={ROTATE}",
    ]

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, _ = p.communicate(timeout=OCR_TIMEOUT)

    for line in stdout.splitlines():
        try:
            msg = json.loads(line)
            if msg.get("ok"):
                return int(msg["volume"])
        except Exception:
            continue

    raise RuntimeError("OCR failed")


def move_motor(direction, duty, duration_ms):
    dc = ensure_volume_dc()
    dc.run(direction=direction, duty=duty)
    time.sleep(duration_ms / 1000.0)
    dc.stop()


def violates_direction(prev, cur, direction):
    if prev is None:
        return False
    if direction == 0:  # CCW → must decrease
        return cur >= prev
    else:               # CW → must increase
        return cur <= prev


def read_ocr_sane(last_volume):
    cur = read_ocr()

    def out_of_range(v):
        return v < VALID_MIN_UL or v > VALID_MAX_UL

    def jump(a, b):
        return abs(a - b) >= JUMP_THRESHOLD_UL

    if not out_of_range(cur):
        if last_volume is None or not jump(cur, last_volume):
            return cur

    for _ in range(MAX_OCR_RETRY):
        move_motor(NUDGE_DIRECTION, NUDGE_DUTY, NUDGE_DURATION_MS)
        time.sleep(NUDGE_SETTLE_SEC)

        new = read_ocr()
        if not out_of_range(new):
            if last_volume is None or not jump(new, last_volume):
                return new
        cur = new

    return last_volume if last_volume is not None else cur


# ==========================================================
# Batch main
# ==========================================================
def batch_random_test():
    ensure_dirs()
    idx = get_next_snapshot_index()

    for _ in range(BATCH_COUNT):
        target = random.randrange(TARGET_MIN, TARGET_MAX + 1, 5)
        print(f"\n[BATCH {idx:04d}] target={target}")

        last_volume = None
        same_ocr_count = 0

        for step in range(MAX_ITER):
            cur = read_ocr_sane(last_volume)

            if last_volume is not None and cur == last_volume:
                same_ocr_count += 1
            else:
                same_ocr_count = 0

            if same_ocr_count >= MAX_SAME_OCR_COUNT:
                print(f"[BATCH {idx:04d}] ❌ OCR STUCK → skip")
                break

            err = target - cur
            print(f"  step={step} target={target} cur={cur} err={err}")

            if abs(err) <= VOLUME_TOLERANCE:
                print("  ✅ reached")
                save_snapshot(idx, target)
                break

            direction = 0 if err < 0 else 1
            abs_err = abs(err)

            if abs_err >= 300:
                duty, dur = 60, 500
            elif abs_err >= 100:
                duty, dur = 45, 250
            elif abs_err >= 30:
                duty, dur = 35, 200
            else:
                duty, dur = 25, 150

            move_motor(direction, duty, dur)
            time.sleep(SETTLE_TIME)

            # Direction consistency check
            new_cur = read_ocr_sane(cur)
            retry = 0
            while violates_direction(cur, new_cur, direction) and retry < MAX_DIR_MISMATCH_RETRY:
                print("[DIR-WARN] direction mismatch → nudge")
                move_motor(direction, NUDGE_DUTY, NUDGE_DURATION_MS)
                time.sleep(NUDGE_SETTLE_SEC)
                new_cur = read_ocr_sane(cur)
                retry += 1

            last_volume = new_cur

        idx += 1
        time.sleep(INTER_RUN_DELAY_SEC)


if __name__ == "__main__":
    batch_random_test()
