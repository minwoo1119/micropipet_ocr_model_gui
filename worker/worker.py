import argparse
import json
import os
import cv2
import time

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
    ap.add_argument("--strength", type=int, default=30)   # duty
    ap.add_argument("--duration", type=int, default=200)  # ms (Python sleep)


    # ---- Linear actuator semantic actions ----
    ap.add_argument("--linear-pipetting-up", action="store_true")
    ap.add_argument("--linear-pipetting-down", action="store_true")

    ap.add_argument("--tip-change-up", action="store_true")
    ap.add_argument("--tip-change-down", action="store_true")

    ap.add_argument("--run-target", action="store_true")
    ap.add_argument("--target", type=int, default=0)

    ap.add_argument("--linear-move", action="store_true")
    ap.add_argument("--actuator-id", type=lambda x: int(x, 0))
    ap.add_argument("--position", type=int)


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
        rois, annotated_path = run_yolo_on_frame(frame)
        print(json.dumps(
            {"ok": True, "rois": rois, "annotated_path": annotated_path},
            ensure_ascii=False
        ))
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
            # ▶ 모터 구동 (대표님 프로토콜: dir + duty)
            ser.run_motor(
                direction=args.direction,
                duty=args.strength,
            )

            # ▶ Python에서 시간 제어
            time.sleep(args.duration / 1000.0)

            # ▶ 정지 (duty = 0)
            ser.run_motor(
                direction=args.direction,
                duty=0,
            )

        finally:
            ser.close()

        print(json.dumps({"ok": True}, ensure_ascii=False))
        return

    # --- run to target ---
    if args.run_target:
        run_to_target(target=args.target, camera_index=args.camera)
        print(json.dumps({"ok": True, "done": True}, ensure_ascii=False))
        return
    
    # --- linear actuator move ---
    if args.linear_move:
        ser = SerialController()
        if not ser.connect():
            print(json.dumps({"ok": False, "error": "serial connect failed"}))
            return

        try:
            from worker.actuator_linear import LinearActuator
            act = LinearActuator(
                serial=ser,
                actuator_id=args.actuator_id,
            )

            act.move_to(args.position)
        finally:
            ser.close()

        print(json.dumps({
            "ok": True,
            "actuator_id": args.actuator_id,
            "position": args.position,
        }))
        return


        # =================================================
    # Linear actuator – semantic actions
    # =================================================
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

            # 펌웨어 기준:
            # 0x0B = Pipetting & TipChange Linear
            act = LinearActuator(
                serial=ser,
                actuator_id=0x0B,
            )

            # TODO: 실제 값은 INI / config로 빼는 게 이상적
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


    print(json.dumps({"ok": False, "error": "no action specified"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
