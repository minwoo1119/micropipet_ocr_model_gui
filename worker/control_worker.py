import time

from worker.camera import capture_one_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator
from worker.actuator_linear import LinearActuator
from worker.paths import OCR_TRT_PATH


# ================== Tuning Parameters ==================
VOLUME_TOLERANCE = 1
SETTLE_TIME = 0.7
MAX_DUTY = 60


def run_to_target(
    target: int,
    camera_index: int = 0,
    max_iter: int = 60,
):
    print("[RUN] run_to_target started")

    # ---------- OCR ----------
    trt_model = TRTWrapper(OCR_TRT_PATH)

    # ---------- Serial ----------
    ser = SerialController()
    if not ser.connect():
        raise RuntimeError("Serial connect failed")

    # ---------- Actuators ----------
    volume_motor = VolumeDCActuator(
        serial=ser,
        actuator_id=0x0C,   # 대표님 코드: ACTUATOR_ID_VOLUMECHANGEDCMOTOR
    )

    try:
        for step in range(max_iter):
            frame = capture_one_frame(camera_index)
            cur_volume = int(read_volume_trt(frame, trt_model))
            err = target - cur_volume

            print(
                f"[STEP {step:02d}] "
                f"target={target:04d} "
                f"cur={cur_volume:04d} "
                f"err={err:+d}"
            )

            if abs(err) <= VOLUME_TOLERANCE:
                print("[DONE] Target volume reached")
                break

            # -------- Control policy --------
            direction = 0 if err < 0 else 1
            abs_err = abs(err)

            if abs_err >= 300:
                duty = 60
                duration = 300
            elif abs_err >= 100:
                duty = 45
                duration = 250
            elif abs_err >= 30:
                duty = 35
                duration = 200
            else:
                duty = 25
                duration = 150

            volume_motor.move(
                direction=direction,
                duty=duty,
                duration_ms=duration,
            )

            time.sleep(SETTLE_TIME)

        else:
            print("[WARN] Max iteration reached")

    finally:
        print("[CLEANUP] Stop & close serial")
        try:
            volume_motor.move(direction=0, duty=0, duration_ms=50)
        except Exception:
            pass
        ser.close()
