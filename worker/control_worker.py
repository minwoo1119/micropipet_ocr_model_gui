# worker/control_worker.py
import json
import time
import sys

from worker.camera import capture_one_frame
from worker.ocr_trt import TRTWrapper, read_volume_trt
from worker.paths import OCR_TRT_PATH

VOLUME_TOLERANCE = 1
SETTLE_TIME = 0.7
MAX_ITER = 60


def _elog(msg: str):
    # 사람 로그는 stderr로
    print(msg, file=sys.stderr, flush=True)


def run_to_target(
    target: int,
    camera_index: int = 0,
    max_iter: int = MAX_ITER,
):
    _elog("[RUN] run_to_target started (VISION ONLY)")

    trt_model = TRTWrapper(OCR_TRT_PATH)

    for step in range(max_iter):
        frame = capture_one_frame(camera_index)
        cur_volume = int(read_volume_trt(frame, trt_model))
        err = target - cur_volume

        # 종료 조건
        if abs(err) <= VOLUME_TOLERANCE:
            print(json.dumps({
                "cmd": "done",
                "step": step,
                "current": cur_volume,
                "target": target,
                "error": err,
            }), flush=True)
            _elog("[DONE] target reached")
            break

        direction = 1 if err < 0 else 0
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

        # 사람 로그는 stderr
        _elog(
            f"[STEP {step}] cur={cur_volume} err={err} "
            f"dir={'CCW' if direction==1 else 'CW'} duty={duty} dur={duration_ms}ms"
        )

        # GUI용 JSON은 stdout (✅ 이것만 stdout)
        print(json.dumps({
            "cmd": "volume",
            "step": step,
            "current": cur_volume,
            "target": target,
            "error": err,
            "direction": direction,
            "duty": duty,
            "duration_ms": duration_ms,
        }), flush=True)

        time.sleep(SETTLE_TIME)

    else:
        print(json.dumps({
            "cmd": "warn",
            "status": "max_iter"
        }), flush=True)
        _elog("[WARN] max_iter reached")

    _elog("[CLEANUP] run_to_target finished")
