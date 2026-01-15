# test/single_target_test.py
import subprocess
import json
import time
import os
import sys
import cv2

from worker.capture_frame import OUTPUT_PATH
from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator

# ==========================================================
# Config
# ==========================================================
SNAP_DIR = "snapshots"

VOLUME_TOLERANCE = 1
SETTLE_TIME = 0.9
MAX_ITER = 60
OCR_TIMEOUT = 20

VALID_MIN_UL = 500
VALID_MAX_UL = 5000
JUMP_THRESHOLD_UL = 200
MAX_OCR_RETRY = 4

NUDGE_DUTY = 25
NUDGE_DURATION_MS = 60
NUDGE_DIRECTION = 1
NUDGE_SETTLE_SEC = 0.15

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


def save_snapshot(order: int, value_ul: int, rotate: int = 1):
    fname = f"{order:04d}_{value_ul:04d}.jpg"
    dst = os.path.join(SNAP_DIR, fname)

    img = cv2.imread(OUTPUT_PATH)
    if img is None:
        raise RuntimeError("snapshot source missing")

    if rotate == 1:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif rotate == 2:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotate == 3:
        img = cv2.rotate(img, cv2.ROTATE_180)

    cv2.imwrite(dst, img)
    print(f"[SNAPSHOT] saved → {dst}")


# ==========================================================
# OCR (1회용 subprocess)
# ==========================================================
def read_ocr_volume(camera_index=0, rotate=1) -> int:
    cmd = [
        sys.executable, "-m", "worker.worker",
        "--ocr",
        f"--camera={camera_index}",
        f"--rotate={rotate}",
    ]

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        stdout, _ = p.communicate(timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        raise RuntimeError("OCR timeout")

    for line in stdout.splitlines():
        try:
            msg = json.loads(line)
            if msg.get("ok"):
                return int(msg["volume"])
        except Exception:
            continue

    raise RuntimeError("OCR failed")


def move_motor(direction: int, duty: int, duration_ms: int):
    dc = ensure_volume_dc()
    dc.run(direction=direction, duty=duty)
    time.sleep(duration_ms / 1000.0)
    dc.stop()


def read_ocr_volume_sane(last_volume, camera_index=0, rotate=1):
    cur = read_ocr_volume(camera_index, rotate)

    def out_of_range(v):
        return v < VALID_MIN_UL or v > VALID_MAX_UL

    def jump(a, b):
        return abs(a - b) >= JUMP_THRESHOLD_UL

    if not out_of_range(cur):
        if last_volume is None or not jump(cur, last_volume):
            return cur

    print(f"[OCR-WARN] unstable OCR: {cur}")

    for _ in range(MAX_OCR_RETRY):
        move_motor(NUDGE_DIRECTION, NUDGE_DUTY, NUDGE_DURATION_MS)
        time.sleep(NUDGE_SETTLE_SEC)
        new = read_ocr_volume(camera_index, rotate)
        if not out_of_range(new):
            if last_volume is None or not jump(new, last_volume):
                return new
        cur = new

    return last_volume if last_volume is not None else cur


def single_target_test(target_ul, camera_index=0, rotate=1):
    print(f"[TEST] target={target_ul}")
    last_volume = None

    for step in range(MAX_ITER):
        cur = read_ocr_volume_sane(last_volume, camera_index, rotate)
        last_volume = cur
        err = target_ul - cur

        print(f"[STEP {step}] cur={cur} err={err}")

        if abs(err) <= VOLUME_TOLERANCE:
            return {
                "success": True,
                "final_ul": cur,
                "target_ul": target_ul,
                "steps": step + 1,
            }

        direction = 0 if err < 0 else 1
        abs_err = abs(err)

        if abs_err >= 300:
            duty, dur = 55, 280
        elif abs_err >= 150:
            duty, dur = 45, 240
        elif abs_err >= 50:
            duty, dur = 35, 200
        else:
            duty, dur = 30, 150


        move_motor(direction, duty, dur)
        time.sleep(SETTLE_TIME)

    return {
        "success": False,
        "final_ul": last_volume,
        "target_ul": target_ul,
        "reason": "max_iter",
    }
