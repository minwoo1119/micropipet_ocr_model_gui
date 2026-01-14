# worker/dataset_collector.py
import os
import time
import random
import cv2

from worker.camera import capture_one_frame
from worker.ocr_trt import read_volume_trt
from worker.actuator_volume_dc import VolumeDCActuator
from worker.paths import ROIS_JSON_PATH

import json

DATASET_ROOT = "dataset"
CAPTURE_INTERVAL = 0.5   # sec
MIN_CONF = 0.85          # OCR confidence threshold


def load_rois():
    with open(ROIS_JSON_PATH, "r") as f:
        return json.load(f)


def ensure_dirs():
    for i in range(10):
        os.makedirs(os.path.join(DATASET_ROOT, str(i)), exist_ok=True)


def random_motor_move(actuator: VolumeDCActuator):
    """
    소량 랜덤 회전
    """
    step = random.randint(-15, 15)   # tick or degree 단위
    actuator.move_relative(step)
    time.sleep(0.2)


def collect_once(actuator, rois, ocr):
    random_motor_move(actuator)

    frame = capture_one_frame(0)

    for roi in rois:
        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
        crop = frame[y:y+h, x:x+w]

        if crop.size == 0:
            continue

        pred, conf = read_volume_trt(ocr, crop, return_conf=True)

        if pred is None or conf < MIN_CONF:
            continue

        label = str(pred)
        ts = int(time.time() * 1000)
        save_path = os.path.join(
            DATASET_ROOT, label, f"{label}_{ts}.png"
        )
        cv2.imwrite(save_path, crop)
        print(f"[SAVE] {save_path} (conf={conf:.2f})")


def run_dataset_collection(actuator, ocr, max_iter=None):
    ensure_dirs()
    rois = load_rois()

    i = 0
    while True:
        collect_once(actuator, rois, ocr)
        i += 1

        if max_iter and i >= max_iter:
            break

        time.sleep(CAPTURE_INTERVAL)
