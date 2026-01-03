import argparse
import json
import os
import cv2

from worker.paths import (
    ensure_state_dir, FRAME_JPG_PATH, ROIS_JSON_PATH
)
from worker.camera import capture_one_frame
from worker.yolo_worker import run_yolo_on_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.paths import OCR_TRT_PATH
from worker.serial_controller import SerialController
from worker.control_worker import run_to_target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)

    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--reset-rois", action="store_true")
    ap.add_argument("--ocr", action="store_true")

    ap.add_argument("--motor-test", action="store_true")
    ap.add_argument("--direction", type=int, default=0)
    ap.add_argument("--strength", type=int, default=30)
    ap.add_argument("--duration", type=int, default=200)

    ap.add_argument("--run-target", action="store_true")
    ap.add_argument("--target", type=int, default=0)

    args = ap.parse_args()

    ensure_state_dir()

    # reset rois
    if args.reset_rois and os.path.exists(ROIS_JSON_PATH):
        try:
            os.remove(ROIS_JSON_PATH)
        except Exception:
            pass

    # --- capture ---
    if args.capture:
        frame = capture_one_frame(args.camera)
        cv2.imwrite(FRAME_JPG_PATH, frame)
        print(json.dumps({"ok": True, "frame_path": FRAME_JPG_PATH}, ensure_ascii=False))
        return

    # --- yolo ---
    if args.yolo:
        frame = capture_one_frame(args.camera)
        rois, annotated_path = run_yolo_on_frame(frame, show_window=True)
        print(json.dumps({"ok": True, "rois": rois, "annotated_path": annotated_path}, ensure_ascii=False))
        return

    # --- ocr ---
    if args.ocr:
        trt_model = TRTWrapper(OCR_TRT_PATH)
        frame = capture_one_frame(args.camera)
        vol = read_volume_trt(frame, trt_model)
        print(json.dumps({"ok": True, "volume": int(vol)}, ensure_ascii=False))
        return

    # --- motor test ---
    if args.motor_test:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}, ensure_ascii=False))
            return
        try:
            ser.send_motor_command(args.direction, args.strength, args.duration)
        finally:
            ser.close()
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return

    # --- run to target ---
    if args.run_target:
        run_to_target(target=args.target, camera_index=args.camera)
        print(json.dumps({"ok": True, "done": True}, ensure_ascii=False))
        return

    print(json.dumps({"ok": False, "error": "no action specified"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
