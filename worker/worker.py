import argparse

from yolo_worker import run_yolo
from motor_controller import motor_test, run_to_target

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yolo", action="store_true")
    parser.add_argument("--reset", action="store_true")

    parser.add_argument("--target", type=float)

    parser.add_argument("--motor-test", action="store_true")
    parser.add_argument("--dir", type=str, default="CW")
    parser.add_argument("--power", type=int, default=50)
    parser.add_argument("--time", type=float, default=2.0)

    args = parser.parse_args()

    if args.yolo:
        run_yolo(reset=args.reset)

    elif args.target is not None:
        run_to_target(args.target)

    elif args.motor_test:
        motor_test(args.dir, args.power, args.time)

if __name__ == "__main__":
    main()
