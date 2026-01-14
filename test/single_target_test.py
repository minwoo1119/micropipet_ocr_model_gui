# test/single_target_test.py
import subprocess
import json
import time
import os
import shutil
import sys

from worker.capture_frame import OUTPUT_PATH
from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator

# ==========================================================
# Config
# ==========================================================
SNAP_DIR = "snapshots"

VOLUME_TOLERANCE = 1   # uL
SETTLE_TIME = 0.7      # sec
MAX_ITER = 60
OCR_TIMEOUT = 20       # sec

# ---------- OCR sanity check ----------
JUMP_THRESHOLD_UL = 200     # 이전 값 대비 급변 허용 한계
MAX_OCR_RETRY = 2           # nudge 후 재시도 횟수
NUDGE_DUTY = 18             # 아주 약한 duty
NUDGE_DURATION_MS = 70
NUDGE_DIRECTION = 1         # 환경에 맞게 0/1 조정
NUDGE_SETTLE_SEC = 0.15

# ==========================================================
# Global actuator (GUI와 동일 경로)
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


def save_snapshot(order: int, value_ul: int):
    fname = f"{order:04d}_{value_ul/1000:.3f}.jpg"
    dst = os.path.join(SNAP_DIR, fname)
    shutil.copy(OUTPUT_PATH, dst)
    print(f"[TEST] snapshot saved: {dst}")


# ==========================================================
# OCR (GUI Read OCR Volume과 동일 경로)
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
        stdout, stderr = p.communicate(timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        raise RuntimeError("OCR subprocess timeout")

    for line in stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if msg.get("ok"):
            return int(msg["volume"])

    raise RuntimeError(
        f"OCR failed\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


# ==========================================================
# Motor control (GUI PipettePanel과 동일)
# ==========================================================
def move_motor(direction: int, duty: int, duration_ms: int):
    volume_dc = ensure_volume_dc()

    print(
        f"[MOTOR] run dir={'CW' if direction==1 else 'CCW'} "
        f"duty={duty} duration={duration_ms}ms"
    )

    volume_dc.run(direction=direction, duty=duty)
    time.sleep(duration_ms / 1000.0)
    volume_dc.stop()


# ==========================================================
# OCR sanity wrapper (🔥 핵심 추가)
# ==========================================================
def read_ocr_volume_sane(
    last_volume: int | None,
    camera_index=0,
    rotate=1,
) -> int:
    cur = read_ocr_volume(camera_index=camera_index, rotate=rotate)

    if last_volume is None:
        return cur

    def is_jump(a, b):
        return abs(a - b) >= JUMP_THRESHOLD_UL

    if not is_jump(cur, last_volume):
        return cur

    print(
        f"[OCR-WARN] jump detected: prev={last_volume} now={cur} "
        f"(>= {JUMP_THRESHOLD_UL})"
    )

    for retry in range(MAX_OCR_RETRY):
        print(f"[OCR-NUDGE] retry {retry+1}")

        move_motor(
            direction=NUDGE_DIRECTION,
            duty=NUDGE_DUTY,
            duration_ms=NUDGE_DURATION_MS,
        )
        time.sleep(NUDGE_SETTLE_SEC)

        new_cur = read_ocr_volume(camera_index=camera_index, rotate=rotate)
        print(f"[OCR-RETRY] value={new_cur}")

        if not is_jump(new_cur, last_volume):
            return new_cur

        cur = new_cur

    print("[OCR-WARN] unstable OCR → using last_volume for safety")
    return last_volume


# ==========================================================
# Single target test
# ==========================================================
def single_target_test(
    target_ul: int,
    camera_index: int = 0,
    rotate: int = 1,
):
    print("[TEST] Single target test (worker-only)")
    print(f"[TEST] Target = {target_ul} uL")

    last_volume = None

    for step in range(MAX_ITER):
        # --------------------------------------------------
        # 1. OCR (sanity-aware)
        # --------------------------------------------------
        cur = read_ocr_volume_sane(
            last_volume=last_volume,
            camera_index=camera_index,
            rotate=rotate,
        )

        last_volume = cur
        err = target_ul - cur

        print(
            f"[STEP {step}] "
            f"cur={cur} target={target_ul} err={err}"
        )

        # --------------------------------------------------
        # 2. 종료 조건
        # --------------------------------------------------
        if abs(err) <= VOLUME_TOLERANCE:
            print("[DONE] Target reached")
            return {
                "success": True,
                "final_ul": cur,
                "target_ul": target_ul,
                "steps": step + 1,
            }

        # --------------------------------------------------
        # 3. 제어 로직
        # --------------------------------------------------
        direction = 0 if err < 0 else 1
        abs_err = abs(err)

        if abs_err >= 300:
            duty = 60
            duration_ms = 300
        elif abs_err >= 100:
            duty = 45
            duration_ms = 250
        elif abs_err >= 30:
            duty = 35
            duration_ms = 200
        else:
            duty = 25
            duration_ms = 150

        # --------------------------------------------------
        # 4. Motor
        # --------------------------------------------------
        move_motor(
            direction=direction,
            duty=duty,
            duration_ms=duration_ms,
        )

        # --------------------------------------------------
        # 5. settle
        # --------------------------------------------------
        time.sleep(SETTLE_TIME)

    print("[WARN] max_iter reached")
    return {
        "success": False,
        "final_ul": last_volume,
        "target_ul": target_ul,
        "reason": "max_iter",
    }


# ==========================================================
# Entry
# ==========================================================
def main():
    ensure_dirs()

    target_ul = 1200

    result = single_target_test(
        target_ul=target_ul,
        camera_index=0,
        rotate=1,
    )

    print("\n========== RESULT ==========")
    print(result)

    if result.get("success"):
        save_snapshot(order=1, value_ul=result["final_ul"])
    else:
        print("❌ Failed to reach target")


if __name__ == "__main__":
    main()
