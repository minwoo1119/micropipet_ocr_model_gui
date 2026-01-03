import cv2
import os

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "shared",
    "latest_frame.jpg"
)

def capture_one_frame(camera_index=0):
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        raise RuntimeError("Camera open failed")

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("Frame capture failed")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cv2.imwrite(OUTPUT_PATH, frame)
    print(f"[worker] frame saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    capture_one_frame()
