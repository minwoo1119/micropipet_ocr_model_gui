# test/batch_random_test.py
import time
import random
import os

from test.single_target_test import (
    single_target_test,
    save_snapshot,
    ensure_dirs,
)

SNAP_DIR = "snapshots"

BATCH_COUNT = 1000
TARGET_MIN = 1000
TARGET_MAX = 4500
TARGET_STEP = 5

CAMERA_INDEX = 0
ROTATE = 1
INTER_RUN_DELAY_SEC = 1.0


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


def batch_random_test():
    ensure_dirs()
    idx = get_next_snapshot_index()

    print("====================================")
    print("[BATCH] start random batch test")
    print(f"[BATCH] count={BATCH_COUNT}")
    print("====================================")

    for run in range(BATCH_COUNT):
        target_ul = random.randrange(
            TARGET_MIN,
            TARGET_MAX + 1,
            TARGET_STEP,
        )

        print(
            f"\n[BATCH {idx:04d}] "
            f"run={run + 1}/{BATCH_COUNT} "
            f"target={target_ul}"
        )

        result = single_target_test(
            target_ul=target_ul,
            camera_index=CAMERA_INDEX,
            rotate=ROTATE,
        )

        if result.get("success"):
            final_ul = result["final_ul"]
            print(f"[BATCH {idx:04d}] ✅ success final={final_ul}")
            save_snapshot(idx, final_ul, rotate=ROTATE)
            idx += 1
        else:
            print(
                f"[BATCH {idx:04d}] ❌ failed "
                f"reason={result.get('reason')}"
            )

        time.sleep(INTER_RUN_DELAY_SEC)

    print("\n[BATCH] finished all runs")


if __name__ == "__main__":
    batch_random_test()