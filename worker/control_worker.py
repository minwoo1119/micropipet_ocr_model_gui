import time

from worker.camera import capture_one_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.serial_controller import SerialController
from worker.paths import OCR_TRT_PATH


# ================== Tuning Parameters ==================
# OCR volume error -> motor position gain
VOLUME_TO_POSITION_GAIN = 2.5   # 실험으로 반드시 튜닝

# Max position change per step (safety)
MAX_POSITION_STEP = 120

# Acceptable volume tolerance
VOLUME_TOLERANCE = 1

# Mechanical settling time (sec)
SETTLE_TIME = 0.7


def run_to_target(
    target: int,
    camera_index: int = 0,
    max_iter: int = 60,
):

    print("[RUN] run_to_target started")

    # ---------- Load OCR (TensorRT) ----------
    trt_model = TRTWrapper(OCR_TRT_PATH)

    # ---------- Serial ----------
    ser = SerialController()
    if not ser.connect():
        raise RuntimeError("Serial connect failed")

    # ---------- Initial motor setup ----------
    ser.set_speed(400)     # RPM
    ser.set_torque(350)    # Current

    current_position = 0

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

            delta_pos = int(err * VOLUME_TO_POSITION_GAIN)

            if delta_pos > MAX_POSITION_STEP:
                delta_pos = MAX_POSITION_STEP
            elif delta_pos < -MAX_POSITION_STEP:
                delta_pos = -MAX_POSITION_STEP

            current_position += delta_pos

            print(
                f"        Δpos={delta_pos:+d}, "
                f"cmd_pos={current_position}"
            )

            ser.set_position(current_position)

            time.sleep(SETTLE_TIME)

        else:
            print("[WARN] Max iteration reached without convergence")

    finally:
        print("[CLEANUP] Stop motor & close serial")
        try:
            # 안전하게 정지
            ser.set_speed(0)
        except Exception:
            pass
        ser.close()
