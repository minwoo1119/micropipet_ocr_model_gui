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

# ==========================================================
# Global actuator (GUI와 동일 경로)
# ==========================================================
_serial = None
_volume_dc = None


def ensure_dirs():
    os.makedirs(SNAP_DIR, exist_ok=True)


def ensure_volume_dc():
    """
    GUI PipettePanel과 동일한 DC 회전 모터 경로
    """
    global _serial, _volume_dc

    if _serial is None:
        _serial = SerialController()

    if _volume_dc is None:
        _volume_dc = VolumeDCActuator(
            serial=_serial,
            actuator_id=0x0C,   # GUI와 동일
        )

    return _volume_dc


def save_snapshot(order: int, value_ul: int):
    """
    latest_frame.jpg는 이미 OCR 기준 회전 이미지
    그대로 복사만 한다
    """
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
    """
    GUI PipettePanel._rotary_start()와 동일한 동작
    - run(direction, duty)
    - duration 유지
    - stop()
    """
    volume_dc = ensure_volume_dc()

    print(
        f"[MOTOR] run dir={'CW' if direction==1 else 'CCW'} "
        f"duty={duty} duration={duration_ms}ms"
    )

    volume_dc.run(direction=direction, duty=duty)
    time.sleep(duration_ms / 1000.0)
    volume_dc.stop()


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
        # 1. OCR
        # --------------------------------------------------
        cur = read_ocr_volume(
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
        # 3. 제어 로직 (기존 run_to_target 동일)
        # --------------------------------------------------
        direction = 1 if err < 0 else 0
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
