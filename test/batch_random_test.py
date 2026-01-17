import time
import random
import os
import cv2

from test.single_target_test import (
    single_target_test,
    run_calibration,
    load_calibration,
    ensure_dirs,
)
from worker.capture_frame import OUTPUT_PATH

# ==========================================================
# Config
# ==========================================================
SNAP_DIR = "snapshots"

BATCH_COUNT = 200
TARGET_MIN = 1000
TARGET_MAX = 4500
TARGET_STEP = 5

CAMERA_INDEX = 0
ROTATE = 1
INTER_RUN_DELAY_SEC = 1.0
SETTLE_TIME = 0.9


# ==========================================================
# Snapshot utils
# ==========================================================
def get_next_snapshot_index():
    if not os.path.exists(SNAP_DIR):
        return 1

    max_idx = 0
    for f in os.listdir(SNAP_DIR):
        if f.endswith(".jpg"):
            try:
                max_idx = max(max_idx, int(f.split("_")[0]))
            except Exception:
                pass
    return max_idx + 1


def save_snapshot(order: int, value_ul: int, rotate: int):
    os.makedirs(SNAP_DIR, exist_ok=True)
    fname = f"{order:04d}_{value_ul:04d}.jpg"
    dst = os.path.join(SNAP_DIR, fname)

    img = cv2.imread(OUTPUT_PATH)
    if img is None:
        print("[SNAPSHOT] frame missing")
        return False

    if rotate == 1:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif rotate == 2:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotate == 3:
        img = cv2.rotate(img, cv2.ROTATE_180)

    cv2.imwrite(dst, img)
    print(f"[SNAPSHOT] saved → {dst}")
    return True


# ==========================================================
# Batch runner
# ==========================================================
def batch_random_test():
    ensure_dirs()
    idx = get_next_snapshot_index()

    print("====================================")
    print("[BATCH] start random batch test")
    print("====================================")

    calib = load_calibration()
    if calib is None:
        calib = run_calibration(CAMERA_INDEX, ROTATE)

    success_count = 0
    trial_count = 0

    while success_count < BATCH_COUNT:
        trial_count += 1

        target = random.randrange(
            TARGET_MIN,
            TARGET_MAX + 1,
            TARGET_STEP,
        )

        print(
            f"\n[BATCH {idx:04d}] "
            f"success={success_count+1}/{BATCH_COUNT} "
            f"trial={trial_count} "
            f"target={target}"
        )

        result = single_target_test(
            target_ul=target,
            calib=calib,
            camera_index=CAMERA_INDEX,
            rotate=ROTATE,
        )

        if result.get("success"):
            final_ul = result["final_ul"]
            print(f"[BATCH {idx:04d}] success final={final_ul}")

            # 프레임 안정화
            time.sleep(SETTLE_TIME)

            if save_snapshot(idx, final_ul, ROTATE):
                idx += 1
                success_count += 1
        else:
            print(
                f"[BATCH {idx:04d}] failed "
                f"reason={result.get('reason')}"
            )

        time.sleep(INTER_RUN_DELAY_SEC)

    print("\n[BATCH] finished")
    print(f"성공 이미지 : {success_count}")


if __name__ == "__main__":
    batch_random_test()
