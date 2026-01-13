import time

from worker.camera import capture_one_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator
from worker.paths import OCR_TRT_PATH


# ================== Tuning Parameters ==================
VOLUME_TOLERANCE = 1        # OCR 단위 오차 허용
SETTLE_TIME = 0.7           # 모터 정지 후 안정화 시간 (중요)
MAX_ITER = 60


def run_to_target(
    target: int,
    camera_index: int = 0,
    max_iter: int = MAX_ITER,
):
    print("[RUN] run_to_target started")

    # ---------- OCR ----------
    trt_model = TRTWrapper(OCR_TRT_PATH)

    # ---------- Serial ----------
    ser = SerialController()
    if not ser.connect():
        raise RuntimeError("Serial connect failed")

    # ---------- Actuator ----------
    volume_motor = VolumeDCActuator(
        serial=ser,
        actuator_id=0x0C,  # ACTUATOR_ID_VOLUMECHANGEDCMOTOR
    )

    try:
        for step in range(max_iter):
            # ===== 1. Capture & OCR =====
            frame = capture_one_frame(camera_index)
            cur_volume = int(read_volume_trt(frame, trt_model))
            err = target - cur_volume

            print(
                f"[STEP {step:02d}] "
                f"target={target:04d} "
                f"cur={cur_volume:04d} "
                f"err={err:+d}"
            )

            # ===== 2. Termination =====
            if abs(err) <= VOLUME_TOLERANCE:
                print("[DONE] Target volume reached")
                break

            # ===== 3. Control policy =====
            direction = 0 if err < 0 else 1   # 0=CCW, 1=CW
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

            # ===== 4. Motor control (MouseDown) =====
            volume_motor.run(direction=direction, duty=duty)

            # 유지 시간
            time.sleep(duration_ms / 1000.0)

            # ===== 5. Motor stop (MouseUp) =====
            volume_motor.stop()

            # ===== 6. Settle time =====
            time.sleep(SETTLE_TIME)

        else:
            print("[WARN] Max iteration reached")

    finally:
        print("[CLEANUP] Motor stop & serial close")

        # 안전 정지
        try:
            volume_motor.stop()
        except Exception:
            pass

        try:
            ser.close()
        except Exception:
            pass
