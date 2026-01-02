import cv2
from ultralytics import YOLO
from camera import Camera
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "yolo" / "best_rotate_yolo.pt"

def run_yolo(reset=False):
    cam = Camera()
    model = YOLO(MODEL_PATH)

    print("YOLO started")

    while True:
        frame = cam.read()
        if frame is None:
            break

        results = model(frame, verbose=False)
        annotated = results[0].plot()

        cv2.imshow("YOLO Detection", annotated)
        key = cv2.waitKey(1)

        if key == 27:  # ESC
            break
        if reset:
            print("Re-detect triggered")

    cam.release()
    cv2.destroyAllWindows()
