# scripts/collect_dataset.py
from worker.dataset_collector import run_dataset_collection


def main():
    run_dataset_collection(max_iter=500)


if __name__ == "__main__":
    main()
