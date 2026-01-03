import time

from worker.camera import capture_one_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.serial_controller import SerialController
from worker.paths import OCR_TRT_PATH


def run_to_target(target: int, camera_index: int = 0, max_iter: int = 80):
    trt_model = TRTWrapper(OCR_TRT_PATH)

    ser = SerialController()
    if not ser.connect():
        raise RuntimeError("Serial connect failed")

    try:
        for step in range(max_iter):
            frame = capture_one_frame(camera_index)
            cur = read_volume_trt(frame, trt_model)
            err = int(target) - int(cur)
            print(f"[STEP {step}] target={target:04d} cur={cur:04d} err={err:+d}")

            if err == 0:
                print("[DONE] Perfect match.")
                break

            direction = 0 if err > 0 else 1
            abs_err = abs(err)

            # 간단한 펄스 정책(원하면 네 PI 로직으로 교체 가능)
            if abs_err >= 300:
                strength = 70
                duration = 260
            elif abs_err >= 100:
                strength = 55
                duration = 220
            elif abs_err >= 30:
                strength = 40
                duration = 180
            else:
                strength = 30
                duration = 160

            ser.send_motor_command(direction, strength, duration)
            time.sleep(duration / 1000.0 + 0.6)

    finally:
        try:
            ser.send_motor_command(0, 0, 1)
        except Exception:
            pass
        ser.close()
