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
CALIB_JSON_PATH = "calibration.json"

VOLUME_TOLERANCE = 1
SETTLE_TIME = 0.9
MAX_ITER = 60
OCR_TIMEOUT = 20

VALID_MIN_UL = 500
VALID_MAX_UL = 5000
BOUND_MARGIN = 5 

CALIB_TOL = 5
CALIB_MAX_TRY = 6

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
# OCR
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

    stdout, _ = p.communicate(timeout=OCR_TIMEOUT)

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


# ==========================================================
# Calibration JSON utils
# ==========================================================
def save_calibration(calib: dict):
    to_save = {str(k): v for k, v in calib.items()}
    with open(CALIB_JSON_PATH, "w") as f:
        json.dump(to_save, f, indent=2)
    print(f"[CALIB] saved → {CALIB_JSON_PATH}")


def load_calibration():
    if not os.path.exists(CALIB_JSON_PATH):
        return None

    with open(CALIB_JSON_PATH, "r") as f:
        raw = json.load(f)

    calib = {int(k): v for k, v in raw.items()}
    print(f"[CALIB] loaded ← {CALIB_JSON_PATH}")
    return calib


# ==========================================================
# Calibration core
# ==========================================================
def calibrate_one_target(
    target_ul: int,
    base_duty: int,
    base_dur: int,
    camera_index: int,
    rotate: int,
):
    print(f"[CALIB] target={target_ul}uL")

    duty = base_duty
    dur = base_dur

    for i in range(CALIB_MAX_TRY):
        before = read_ocr_volume(camera_index, rotate)
        move_motor(1, duty, dur)
        time.sleep(SETTLE_TIME)
        after = read_ocr_volume(camera_index, rotate)

        delta = abs(after - before)

        print(
            f"[CALIB] try={i+1} "
            f"duty={duty} dur={dur}ms delta={delta}"
        )

        if abs(delta - target_ul) <= CALIB_TOL:
            print("[CALIB] accepted")
            return {
                "duty": duty,
                "duration_ms": dur,
                "delta_ul": delta,
            }

        if delta < target_ul:
            dur += 80
        else:
            dur -= 60

        dur = max(80, min(1500, dur))

    raise RuntimeError(f"[CALIB] failed for {target_ul}uL")


def run_calibration(camera_index=0, rotate=1):
    print("=" * 40)
    print("[CALIB] start calibration (one-time)")
    print("=" * 40)

    calib = {}

    calib[100] = calibrate_one_target(100, 55, 900, camera_index, rotate)
    calib[50]  = calibrate_one_target(50,  40, 500, camera_index, rotate)
    calib[10]  = calibrate_one_target(10,  30, 150, camera_index, rotate)
    calib[5]   = calibrate_one_target(5,   25, 80,  camera_index, rotate)

    print("[CALIB] DONE")
    for k, v in calib.items():
        print(f"  {k}uL → {v}")

    save_calibration(calib)
    return calib


# ==========================================================
# Single target control
# ==========================================================
def single_target_test(
    target_ul: int,
    calib: dict,
    camera_index: int = 0,
    rotate: int = 1,
):
    print(f"[TEST] target={target_ul}")

    for step in range(MAX_ITER):
        cur = read_ocr_volume(camera_index, rotate)
        err = target_ul - cur

        print(f"[STEP {step}] cur={cur} err={err}")

        if abs(err) <= VOLUME_TOLERANCE:
            return {
                "success": True,
                "final_ul": cur,
                "target_ul": target_ul,
                "steps": step + 1,
            }

        # HARD BOUND
        if cur <= VALID_MIN_UL + BOUND_MARGIN and err < 0:
            print("[BOUND] lower limit reached")
            break
        if cur >= VALID_MAX_UL - BOUND_MARGIN and err > 0:
            print("[BOUND] upper limit reached")
            break

        abs_err = abs(err)
        direction = 0 if err < 0 else 1

        if abs_err >= 110:
            cfg = calib[100]
        elif abs_err >= 60:
            cfg = calib[50]
        elif abs_err >= 12:
            cfg = calib[10]
        else:
            cfg = calib[5]

        move_motor(direction, cfg["duty"], cfg["duration_ms"])
        time.sleep(SETTLE_TIME)

    return {
        "success": False,
        "final_ul": cur,
        "target_ul": target_ul,
        "reason": "max_iter_or_bound",
    }
