import os
import cv2
import json
import torch
import numpy as np
import timm

from worker.paths import YOLO_MODEL_PATH, FRAME_JPG_PATH

# ==============================
# CONFIG
# ==============================
CAMERA_INDEX = 0
FRAME_SIZE = (1280, 800)

OCR_PT_PATH = "/home/sixr/Desktop/pipet_model/ocr_motor/best_efficientnet_origin.pt"
NUM_CLASSES = 10

INPUT_SIZE = (224, 224)
NORM_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
NORM_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# ==============================
# OCR utils
# ==============================
def pad_to_square(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    size = max(h, w)
    canvas = np.zeros((size, size, 3), dtype=img.dtype)
    y_offset = (size - h) // 2
    x_offset = (size - w) // 2
    canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img
    return canvas


def preprocess_roi(roi_bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, INPUT_SIZE, interpolation=cv2.INTER_LINEAR)
    x = resized.astype(np.float32) / 255.0
    x = (x - NORM_MEAN) / NORM_STD
    x = np.transpose(x, (2, 0, 1))  # CHW
    return x


def load_ocr_model():
    model = timm.create_model(
        "efficientnet_b0",
        pretrained=False,
        num_classes=NUM_CLASSES,
    )

    ckpt = torch.load(OCR_PT_PATH, map_location="cpu")
    state_dict = ckpt["model"] if "model" in ckpt else ckpt
    model.load_state_dict(state_dict)
    model.eval()
    return model


# ==============================
# YOLO utils
# ==============================
def run_yolo(frame):
    from ultralytics import YOLO

    model = YOLO(YOLO_MODEL_PATH)
    results = model(frame, verbose=False)[0]

    rois = []
    for box in results.boxes.xywh.cpu().numpy():
        x, y, w, h = box
        rois.append([
            int(x - w / 2),
            int(y - h / 2),
            int(w),
            int(h),
        ])

    # 위 → 아래 정렬
    rois = sorted(rois, key=lambda r: r[1])
    return rois


# ==============================
# MAIN
# ==============================
def main():
    print("=== YOLO + OCR ONE SHOT (PREVIEW) ===")

    # ---------------------------------
    # 1. Capture frame
    # ---------------------------------
    from worker.camera import capture_one_frame
    frame = capture_one_frame(CAMERA_INDEX)

    cv2.imwrite(FRAME_JPG_PATH, frame)
    h, w = frame.shape[:2]

    # ---------------------------------
    # 2. YOLO detect
    # ---------------------------------
    rois = run_yolo(frame)

    print(f"[YOLO] detected {len(rois)} boxes")

    # ---------------------------------
    # 3. Draw YOLO preview
    # ---------------------------------
    preview = frame.copy()
    for i, (x, y, rw, rh) in enumerate(rois):
        cv2.rectangle(preview, (x, y), (x+rw, y+rh), (0, 255, 0), 2)
        cv2.putText(
            preview, f"ROI{i}",
            (x, y-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (0, 255, 0), 2
        )

    cv2.imshow("YOLO ROI Preview", preview)

    # ---------------------------------
    # 4. OCR inference (PT)
    # ---------------------------------
    model = load_ocr_model()
    digits = []
    ocr_results = []

    for i, (x, y, rw, rh) in enumerate(rois):
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))
        crop = frame[y:y+rh, x:x+rw]

        if crop.size == 0:
            print(f"[WARN] ROI{i} empty")
            continue

        cv2.imshow(f"OCR ROI {i}", crop)

        x_in = preprocess_roi(crop)
        x_in = torch.from_numpy(x_in).unsqueeze(0).float()

        with torch.no_grad():
            logits = model(x_in)
            prob = torch.softmax(logits, dim=1)
            pred = int(prob.argmax(dim=1))
            conf = float(prob.max(dim=1).values)

        digits.append(pred)
        ocr_results.append((pred, conf))

        print(f"ROI{i}: digit={pred}, conf={conf:.3f}")

    # ---------------------------------
    # 5. Volume 계산 (가능할 때만)
    # ---------------------------------
    if len(digits) == 4:
        volume = (
            digits[0] * 1000 +
            digits[1] * 100 +
            digits[2] * 10 +
            digits[3]
        )
        print(f"\n[VOLUME] {volume}")
    else:
        print("\n[VOLUME] skipped (ROI count != 4)")

    print("\nPress any key to close windows.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
