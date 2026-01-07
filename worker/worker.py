import argparse
import json
import os
import cv2
import time

from worker.paths import (
    ensure_state_dir, FRAME_JPG_PATH, ROIS_JSON_PATH, YOLO_JPG_PATH
)
from worker.camera import capture_one_frame
from worker.yolo_worker import run_yolo_on_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.paths import OCR_TRT_PATH
from worker.serial_controller import SerialController
from worker.control_worker import run_to_target


def rotate_frame(frame, rotate_code: int):
    if rotate_code == 1:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotate_code == 2:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if rotate_code == 3:
        return cv2.rotate(frame, cv2.ROTATE_180)
    return frame


def main():
    ap = argparse.ArgumentParser()

    # -------------------------------------------------
    # Camera / Vision
    # -------------------------------------------------
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--rotate", type=int, default=1)
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--reset-rois", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--ocr-auto-rois", action="store_true")

    # -------------------------------------------------
    # Motor test (DC motor)
    # -------------------------------------------------
    ap.add_argument("--motor-test", action="store_true")
    ap.add_argument("--direction", type=int, default=0)
    ap.add_argument("--strength", type=int, default=30)
    ap.add_argument("--duration", type=int, default=200)

    # -------------------------------------------------
    # Linear actuator semantic actions
    # -------------------------------------------------
    ap.add_argument("--linear-pipetting-up", action="store_true")
    ap.add_argument("--linear-pipetting-down", action="store_true")
    ap.add_argument("--tip-change-up", action="store_true")
    ap.add_argument("--tip-change-down", action="store_true")

    # -------------------------------------------------
    # Target-based control
    # -------------------------------------------------
    ap.add_argument("--run-target", action="store_true")
    ap.add_argument("--target", type=int, default=0)

    # -------------------------------------------------
    # Low-level linear control
    # -------------------------------------------------
    ap.add_argument("--linear-move", action="store_true")
    ap.add_argument("--actuator-id", type=lambda x: int(x, 0))
    ap.add_argument("--position", type=int)

    args = ap.parse_args()
    ensure_state_dir()

    # -------------------------------------------------
    # Reset ROIs
    # -------------------------------------------------
    if args.reset_rois and os.path.exists(ROIS_JSON_PATH):
        try:
            os.remove(ROIS_JSON_PATH)
        except Exception:
            pass

    def capture_rotated():
        frame = capture_one_frame(args.camera)
        return rotate_frame(frame, args.rotate)

    # -------------------------------------------------
    # Capture
    # -------------------------------------------------
    if args.capture:
        frame = capture_rotated()
        cv2.imwrite(FRAME_JPG_PATH, frame)
        print(json.dumps({"ok": True}))
        return

    # -------------------------------------------------
    # YOLO
    # -------------------------------------------------
    if args.yolo:
        frame = capture_rotated()
        cv2.imwrite(FRAME_JPG_PATH, frame)
        rois, annotated_path = run_yolo_on_frame(frame)
        print(json.dumps({"ok": True, "rois": rois}))
        return

    # -------------------------------------------------
    # OCR
    # -------------------------------------------------
    if args.ocr:
        frame = capture_rotated()
        cv2.imwrite(FRAME_JPG_PATH, frame)

        if args.ocr_auto_rois and not os.path.exists(ROIS_JSON_PATH):
            run_yolo_on_frame(frame)

        trt_model = TRTWrapper(OCR_TRT_PATH)
        vol = read_volume_trt(frame, trt_model)
        print(json.dumps({"ok": True, "volume": int(vol)}))
        return

    # -------------------------------------------------
    # Motor test (DC motor)
    # -------------------------------------------------
    if args.motor_test:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False}))
            return

        try:
            ser.send_pipette_change_volume(
                actuator_id=0x0C,
                direction=args.direction,
                duty=args.strength,
            )
            time.sleep(args.duration / 1000.0)
            ser.send_pipette_stop(0x0C)
        finally:
            ser.close()

        print(json.dumps({"ok": True}))
        return

    # -------------------------------------------------
    # Run to target
    # -------------------------------------------------
    if args.run_target:
        run_to_target(target=args.target, camera_index=args.camera)
        print(json.dumps({"ok": True}))
        return

    # -------------------------------------------------
    # Low-level linear move (NO FORCE ON)
    # -------------------------------------------------
    if args.linear_move:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False}))
            return

        try:
            from worker.actuator_linear import LinearActuator

            actuator_id = args.actuator_id if args.actuator_id is not None else 0x0B
            act = LinearActuator(serial=ser, actuator_id=actuator_id)
            act.move_to(args.position)
        finally:
            ser.close()

        print(json.dumps({"ok": True}))
        return

    # -------------------------------------------------
    # Linear semantic actions (C# 동일)
    # -------------------------------------------------
    if (
        args.linear_pipetting_up
        or args.linear_pipetting_down
        or args.tip_change_up
        or args.tip_change_down
    ):
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False}))
            return

        try:
            from worker.actuator_linear import LinearActuator

            actuator_id = 0x0B
            act = LinearActuator(serial=ser, actuator_id=actuator_id)

            ser.send_mightyzap_force_onoff(actuator_id, 1)
            time.sleep(0.15)

            PIPETTING_UP_POS = 1200
            PIPETTING_DOWN_POS = 300
            TIP_CHANGE_UP_POS = 2000
            TIP_CHANGE_DOWN_POS = 400

            if args.linear_pipetting_up:
                act.pipetting_up(PIPETTING_UP_POS)
            elif args.linear_pipetting_down:
                act.pipetting_down(PIPETTING_DOWN_POS)
            elif args.tip_change_up:
                act.tip_change_up(TIP_CHANGE_UP_POS)
            elif args.tip_change_down:
                act.tip_change_down(TIP_CHANGE_DOWN_POS)

        finally:
            ser.close()

        print(json.dumps({"ok": True}))
        return

    print(json.dumps({"ok": False, "error": "no action specified"}))


if __name__ == "__main__":
    main()
