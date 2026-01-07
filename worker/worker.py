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
    """
    rotate_code:
      0 = no rotate
      1 = 90 CW
      2 = 90 CCW
      3 = 180
    """
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
    ap.add_argument("--rotate", type=int, default=1, help="0:none, 1:90CW, 2:90CCW, 3:180")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--reset-rois", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--ocr-auto-rois", action="store_true",
                    help="if rois.json missing, run YOLO first then OCR")

    # -------------------------------------------------
    # Motor test (DC motor)
    # -------------------------------------------------
    ap.add_argument("--motor-test", action="store_true")
    ap.add_argument("--direction", type=int, default=0)
    ap.add_argument("--strength", type=int, default=30)   # duty
    ap.add_argument("--duration", type=int, default=200)  # ms

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

    # -------------------------------------------------
    # MightyZap Force
    # -------------------------------------------------
    ap.add_argument("--linear-force-on", action="store_true")

    # -------------------------------------------------
    # for test
    # -------------------------------------------------
    ap.add_argument("--mz-test", action="store_true")
    ap.add_argument("--mz-speed", type=int, default=500)
    ap.add_argument("--mz-current", type=int, default=300)
    ap.add_argument("--mz-position", type=int, default=2000)

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

    # =================================================
    # Vision common: capture + rotate ONCE
    # =================================================
    def capture_rotated():
        frame = capture_one_frame(args.camera)
        frame = rotate_frame(frame, args.rotate)
        return frame

    # -------------------------------------------------
    # Capture (save rotated frame)
    # -------------------------------------------------
    if args.capture:
        frame = capture_rotated()
        cv2.imwrite(FRAME_JPG_PATH, frame)
        print(json.dumps({"ok": True, "frame_path": FRAME_JPG_PATH}, ensure_ascii=False))
        return

    # -------------------------------------------------
    # YOLO (on rotated frame)
    # -------------------------------------------------
    if args.yolo:
        frame = capture_rotated()
        cv2.imwrite(FRAME_JPG_PATH, frame)  # 디버그/검증용 저장

        rois, annotated_path = run_yolo_on_frame(frame)

        # run_yolo_on_frame 내부에서 annotated 저장을 안 하면,
        # 여기서라도 frame 저장 (YOLO_JPG_PATH는 기존 path에 있음)
        if annotated_path is None:
            cv2.imwrite(YOLO_JPG_PATH, frame)
            annotated_path = YOLO_JPG_PATH

        print(json.dumps(
            {"ok": True, "rois": rois, "annotated_path": annotated_path},
            ensure_ascii=False
        ))
        return

    # -------------------------------------------------
    # OCR (on rotated frame)
    # - 옵션: rois.json 없으면 YOLO 먼저 돌리고 OCR
    # -------------------------------------------------
    if args.ocr:
        frame = capture_rotated()
        cv2.imwrite(FRAME_JPG_PATH, frame)  # OCR도 프레임 저장(검증용)

        if args.ocr_auto_rois and (not os.path.exists(ROIS_JSON_PATH)):
            rois, annotated_path = run_yolo_on_frame(frame)

        trt_model = TRTWrapper(OCR_TRT_PATH)
        vol = read_volume_trt(frame, trt_model)

        print(json.dumps({"ok": True, "volume": int(vol)}, ensure_ascii=False))
        return

    # -------------------------------------------------
    # Force ON (standalone)
    # -------------------------------------------------
    if args.linear_force_on:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}))
            return

        try:
            actuator_id = args.actuator_id if args.actuator_id is not None else 0x0B
            ser.send_mightyzap_force_onoff(
                actuator_id=actuator_id,
                onoff=1,
            )
            time.sleep(0.1)
        finally:
            ser.close()

        print(json.dumps({"ok": True, "force": "on"}))
        return

    # -------------------------------------------------
    # Motor test (DC motor)
    # -------------------------------------------------
    if args.motor_test:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}))
            return

        try:
            ser.send_pipette_change_volume(
                actuator_id=0x0C,
                direction=args.direction,
                duty=args.strength,
            )
            time.sleep(args.duration / 1000.0)
            ser.send_pipette_stop(0x0C)   # ✅ stop 전용 함수 사용
        finally:
            ser.close()

        print(json.dumps({"ok": True}))
        return

    # -------------------------------------------------
    # Run to target (vision-based)
    # -------------------------------------------------
    if args.run_target:
        # run_to_target 내부에서도 capture_one_frame을 쓰면 방향 불일치가 날 수 있음.
        # 가장 안전한 방법은 run_to_target 쪽도 rotate를 받게 고치는 것.
        run_to_target(target=args.target, camera_index=args.camera)
        print(json.dumps({"ok": True, "done": True}, ensure_ascii=False))
        return

    # -------------------------------------------------
    # Low-level linear move
    # -------------------------------------------------
    if args.linear_move:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}))
            return

        try:
            from worker.actuator_linear import LinearActuator

            actuator_id = args.actuator_id if args.actuator_id is not None else 0x0B
            act = LinearActuator(
                serial=ser,
                actuator_id=actuator_id,
            )

            ser.send_mightyzap_force_onoff(actuator_id, 1)
            time.sleep(0.1)

            act.move_to(args.position)
        finally:
            ser.close()

        print(json.dumps({
            "ok": True,
            "actuator_id": actuator_id,
            "position": args.position,
        }))
        return

    # -------------------------------------------------
    # Linear semantic actions
    # -------------------------------------------------
    if (
        args.linear_pipetting_up
        or args.linear_pipetting_down
        or args.tip_change_up
        or args.tip_change_down
    ):
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}))
            return

        try:
            from worker.actuator_linear import LinearActuator

            actuator_id = 0x0B
            act = LinearActuator(serial=ser, actuator_id=actuator_id)

            ser.send_mightyzap_force_onoff(actuator_id, 1)
            time.sleep(0.1)

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

    # -------------------------------------------------
    # MightyZap test
    # -------------------------------------------------
    if args.mz_test:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}))
            return

        try:
            actuator_id = args.actuator_id if args.actuator_id is not None else 0x0B

            ser.send_mightyzap_set_speed(actuator_id, args.mz_speed)
            time.sleep(0.1)

            ser.send_mightyzap_set_current(actuator_id, args.mz_current)
            time.sleep(0.1)

            ser.send_mightyzap_force_onoff(actuator_id, 1)
            time.sleep(0.1)

            ser.send_mightyzap_set_position(actuator_id, args.mz_position)
            time.sleep(0.2)

        finally:
            ser.close()

        print(json.dumps({
            "ok": True,
            "speed": args.mz_speed,
            "current": args.mz_current,
            "position": args.mz_position,
        }))
        return

    # -------------------------------------------------
    # No action
    # -------------------------------------------------
    print(json.dumps({"ok": False, "error": "no action specified"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
