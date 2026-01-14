import time
from worker.control_worker import run_to_target
from test.test_utils import ensure_dirs, take_snapshot

def main():
    ensure_dirs()

    target_ul = 1200  # 🔹 여기서 임시로 목표값 변경
    print(f"[TEST] Run to target: {target_ul} uL")

    start = time.time()

    result = run_to_target(
        target_ul=target_ul,
        tolerance=5,        # 허용 오차 (uL)
        max_loop=100
    )

    elapsed = time.time() - start

    print("[RESULT]", result)
    print(f"[TIME] {elapsed:.2f}s")

    # 최종 도달 시 스냅샷
    take_snapshot(order=1, value_ml=target_ul / 1000)

if __name__ == "__main__":
    main()
