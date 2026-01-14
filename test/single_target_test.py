import time
import os
import shutil

from worker.control_worker import run_to_target
from worker.capture_frame import capture_one_frame_to_disk, OUTPUT_PATH

SNAP_DIR = "snapshots"


def ensure_dirs():
    os.makedirs(SNAP_DIR, exist_ok=True)


def save_gui_frame_snapshot(order, value_ml):
    """
    GUI에서 OCR에 실제로 사용한 프레임(latest_frame.jpg)을 그대로 저장
    """
    fname = f"{order:04d}_{value_ml:.3f}.jpg"
    dst = os.path.join(SNAP_DIR, fname)
    shutil.copy(OUTPUT_PATH, dst)
    print(f"[TEST] snapshot saved: {dst}")


def main():
    ensure_dirs()

    target_ul = 1200
    print(f"[TEST] Run to target (GUI-exact mode): {target_ul} uL")

    capture_one_frame_to_disk(camera_index=0)

    start = time.time()

    result = run_to_target(
        target=target_ul,
        camera_index=0,
    )

    elapsed = time.time() - start

    print("\n========== RESULT ==========")
    print(result)
    print(f"Elapsed: {elapsed:.2f}s")

    if result and result.get("success"):
        save_gui_frame_snapshot(1, target_ul / 1000)
    else:
        print("❌ Failed to reach target")


if __name__ == "__main__":
    main()
