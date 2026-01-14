# worker/dataset_collector.py
import os
import time
import json
import subprocess
import sys
import cv2
import random

from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator
from worker.capture_frame import OUTPUT_PATH
from worker.paths import ROIS_JSON_PATH

# =========================================================
# Config
# =========================================================
DATASET_ROOT = "dataset"      # ocr_motor/dataset/0~9
CAPTURE_INTERVAL = 0.5
OCR_TIMEOUT = 10

# =========================================================
# Global motor (single_target_test 동일)
# =========================================================
_serial = None
_volume_dc = None


def ensure_volume_dc():
    global _serial, _volume_dc

    if _serial is None:
        _serial = SerialController()
        _serial.connect()

    if _volume_dc is None:
        _volume_dc = VolumeDCActuator(
            serial=_serial,
            actuator_id=0x0C,   # single_target_test와 동일
        )

    return _volume_dc


# =========================================================
# ROI
# =========================================================
def load_rois():
    with open(ROIS_JSON_PATH, "r") as f:
        return json.load(f)   # [[x,y,w,h], ...]


def ensure_dirs():
    for i in range(10):
        os.makedirs(os.path.join(DATASET_ROOT, str(i)), exist_ok=True)


# =========================================================
# Motor (GUI / test 동일)
# =========================================================
def random_motor_move():
    motor = ensure_volume_dc()

    direction = random.choice([0, 1])
    duty = random.randint(30, 60)
    duration_ms = random.randint(100, 300)

    motor.run(direction=direction, duty=duty)
    time.sleep(duration_ms / 1000.0)
    motor.stop()


# =========================================================
# ⭐ single_target_test와 동일한 OCR 실행
# =========================================================
def run_ocr():
    cmd = [
        sys.executable,
        "-m", "worker.worker",
        "--ocr",
        "--camera=0",
        "--rotate=1",
    ]

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        p.communicate(timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        print("[WARN] OCR timeout")


# =========================================================
# Collect once
# =========================================================
def collect_once(rois):
    # 1. 모터 랜덤 이동
    random_motor_move()

    # 2. ⭐ single_target_test와 동일한 OCR 경로
    run_ocr()

    # 3. OCR 결과 이미지 로드
    if not os.path.exists(OUTPUT_PATH):
        print("[WARN] latest_frame.jpg not found")
        return

    frame = cv2.imread(OUTPUT_PATH)
    if frame is None:
        print("[WARN] failed to load latest_frame.jpg")
        return

    # 4. ROI crop + 저장
    for (x, y, w, h) in rois:
        crop = frame[y:y+h, x:x+w]
        if crop.size == 0:
            continue

        # 숫자 라벨은 파일명에서 OCR로 읽지 않고
        # "일단 사람이 나중에 분류" or "후처리" 전제
        ts = int(time.time() * 1000)

        # 임시로 unknown → 후처리용
        save_dir = os.path.join(DATASET_ROOT, "unknown")
        os.makedirs(save_dir, exist_ok=True)

        save_path = os.path.join(save_dir, f"{ts}.png")
        cv2.imwrite(save_path, crop)

        print(f"[SAVE] {save_path}")


# =========================================================
# Main loop
# =========================================================
def run_dataset_collection(max_iter=None):
    ensure_dirs()
    rois = load_rois()

    i = 0
    while True:
        collect_once(rois)
        i += 1

        if max_iter and i >= max_iter:
            break

        time.sleep(CAPTURE_INTERVAL)
