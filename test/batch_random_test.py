import time
from worker.control_worker import run_to_target
from test.test_utils import (
    ensure_dirs,
    generate_random_target,
    take_snapshot
)
from test.test_logger import init_log, append_log

TOTAL_TEST = 1000

def main():
    ensure_dirs()
    init_log()

    for order in range(1, TOTAL_TEST + 1):
        target_ul, target_ml = generate_random_target()

        print(f"\n[{order:04d}] Target = {target_ul} uL")

        start = time.time()

        result = run_to_target(
            target_ul=target_ul,
            tolerance=5,
            max_loop=120
        )

        elapsed = time.time() - start

        final_ul = result.get("final_ul")
        success = result.get("success", False)

        # 로그 기록
        append_log(
            order=order,
            target_ul=target_ul,
            target_ml=target_ml,
            final_ul=final_ul,
            success=success,
            elapsed=elapsed
        )

        # 성공 시 스냅샷
        if success:
            path = take_snapshot(order, target_ml)
            print(f"[SNAPSHOT] {path}")
        else:
            print("[FAIL] Did not reach target")

        time.sleep(0.5)  # 기계 안정화용

if __name__ == "__main__":
    main()
