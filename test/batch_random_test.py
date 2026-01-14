# test/batch_random_test.py
import random
import time
import os

from .single_target_test import (
    single_target_test,
    save_snapshot,
    ensure_dirs,
)

# ==========================================================
# Config
# ==========================================================
SNAP_DIR = "snapshots"

BATCH_COUNT = 1000
TARGET_MIN = 500
TARGET_MAX = 5000

INTER_RUN_DELAY_SEC = 1.0   # 각 실험 사이 휴식 (모터/기구 보호)


# ==========================================================
# Snapshot index utility
# ==========================================================
def get_next_snapshot_index(snap_dir: str) -> int:
    """
    snapshots 디렉토리를 스캔하여
    ####_****.jpg 형식의 파일 중 가장 큰 #### 다음 번호 반환
    """
    if not os.path.exists(snap_dir):
        return 1

    max_idx = 0
    for fname in os.listdir(snap_dir):
        if not fname.lower().endswith(".jpg"):
            continue

        try:
            idx = int(fname.split("_")[0])
            max_idx = max(max_idx, idx)
        except Exception:
            continue

    return max_idx + 1


# ==========================================================
# Batch random test
# ==========================================================
def batch_random_test(
    batch_count: int = BATCH_COUNT,
    target_min: int = TARGET_MIN,
    target_max: int = TARGET_MAX,
):
    ensure_dirs()

    start_idx = get_next_snapshot_index(SNAP_DIR)
    print(f"[BATCH] start index = {start_idx:04d}")
    print(f"[BATCH] total runs  = {batch_count}")

    success_count = 0
    fail_count = 0

    for offset in range(batch_count):
        idx = start_idx + offset

        # 🔥 핵심 수정: 마지막 자릿수는 0 또는 5
        target_ul = random.randrange(target_min, target_max + 1, 5)

        print("\n" + "=" * 60)
        print(f"[BATCH {idx:04d}] Target = {target_ul} uL")

        try:
            result = single_target_test(
                target_ul=target_ul,
                camera_index=0,
                rotate=1,
            )

            if result.get("success"):
                success_count += 1
                final_ul = result["final_ul"]

                save_snapshot(
                    order=idx,
                    value_ul=target_ul,   # 파일명은 목표 분주량
                )

                print(
                    f"[BATCH {idx:04d}] ✅ SUCCESS "
                    f"(final={final_ul}, target={target_ul})"
                )
            else:
                fail_count += 1
                print(
                    f"[BATCH {idx:04d}] ❌ FAIL "
                    f"(reason={result.get('reason')})"
                )

        except Exception as e:
            fail_count += 1
            print(f"[BATCH {idx:04d}] ❌ EXCEPTION: {e}")

        # --------------------------------------------------
        # 각 실험 사이 딜레이
        # --------------------------------------------------
        time.sleep(INTER_RUN_DELAY_SEC)

    print("\n" + "=" * 60)
    print("[BATCH DONE]")
    print(f"  Success : {success_count}")
    print(f"  Fail    : {fail_count}")
    print(f"  Total   : {success_count + fail_count}")


# ==========================================================
# Entry
# ==========================================================
if __name__ == "__main__":
    batch_random_test()
