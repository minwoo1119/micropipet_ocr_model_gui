import json
import os
import numpy as np
import cv2
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit  # noqa

from worker.paths import OCR_TRT_PATH, ROIS_JSON_PATH

# =============================
# OCR preprocessing settings (TRAIN/VAL과 동일)
# =============================
INPUT_SIZE = (224, 224)
NORM_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)  # RGB
NORM_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)  # RGB
VOLUME_WEIGHTS = [1000, 100, 10, 1]


# =========================================================
# TensorRT Wrapper
# =========================================================
class TRTWrapper:
    def __init__(self, engine_path: str):
        if not os.path.exists(engine_path):
            raise FileNotFoundError(engine_path)

        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            runtime = trt.Runtime(logger)
            self.engine = runtime.deserialize_cuda_engine(f.read())

        self.context = self.engine.create_execution_context()
        self.stream = cuda.Stream()

        # --- input/output tensor name 잡기 (엔진마다 order가 달라질 수 있어 안전하게) ---
        # 기본: 0=input, 1=output
        self.input_name = None
        self.output_name = None

        # TensorRT 8/9/10 모두 호환되게: tensor 개수만큼 이름 확인
        n_tensors = self.engine.num_io_tensors
        input_candidates = []
        output_candidates = []

        for i in range(n_tensors):
            name = self.engine.get_tensor_name(i)
            mode = self.engine.get_tensor_mode(name)  # trt.TensorIOMode
            if mode == trt.TensorIOMode.INPUT:
                input_candidates.append(name)
            else:
                output_candidates.append(name)

        if len(input_candidates) == 0 or len(output_candidates) == 0:
            # fallback (진짜 특이 케이스)
            self.input_name = self.engine.get_tensor_name(0)
            self.output_name = self.engine.get_tensor_name(1)
        else:
            # 보통 input 1개, output 1개
            self.input_name = input_candidates[0]
            self.output_name = output_candidates[0]

    def infer(self, x_nchw: np.ndarray):
        """
        x_nchw: (N,C,H,W) float32
        return: (cls_list, conf_list, prob_array)
        """
        if x_nchw.dtype != np.float32:
            x_nchw = x_nchw.astype(np.float32)

        N, C, H, W = x_nchw.shape

        # dynamic shape 설정
        self.context.set_input_shape(self.input_name, (N, C, H, W))
        out_shape = tuple(self.context.get_tensor_shape(self.output_name))

        # host/device alloc
        host_input = cuda.pagelocked_empty((N, C, H, W), dtype=np.float32)
        host_output = cuda.pagelocked_empty(out_shape, dtype=np.float32)

        d_input = cuda.mem_alloc(host_input.nbytes)
        d_output = cuda.mem_alloc(host_output.nbytes)

        # bindings set
        self.context.set_tensor_address(self.input_name, int(d_input))
        self.context.set_tensor_address(self.output_name, int(d_output))

        np.copyto(host_input, x_nchw)

        cuda.memcpy_htod_async(d_input, host_input, self.stream)
        self.context.execute_async_v3(stream_handle=self.stream.handle)
        cuda.memcpy_dtoh_async(host_output, d_output, self.stream)
        self.stream.synchronize()

        d_input.free()
        d_output.free()

        # softmax
        logits = host_output.reshape((N, -1))
        e_x = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        prob = e_x / np.sum(e_x, axis=1, keepdims=True)

        cls = prob.argmax(axis=1).astype(int)
        conf = prob[np.arange(N), cls]
        return cls.tolist(), conf.tolist(), prob


# =========================================================
# Image preprocessing helpers (학습 val_tf와 1:1)
# - Resize((224,224)) : 비율 무시
# - ToTensor()
# - Normalize(mean,std) : RGB 기준
# =========================================================
def _preprocess_roi_bgr(roi_bgr: np.ndarray) -> np.ndarray:
    # 1) BGR -> RGB
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)

    # 2) Resize((224,224))  (비율 유지 X, 학습과 동일)
    resized = cv2.resize(rgb, INPUT_SIZE, interpolation=cv2.INTER_LINEAR)

    # 3) ToTensor: [0,1], CHW
    x = resized.astype(np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))  # CHW, RGB

    # 4) Normalize: (x-mean)/std
    # mean/std shape 맞추기: (3,1,1)
    x = (x - NORM_MEAN[:, None, None]) / NORM_STD[:, None, None]

    return x.astype(np.float32)


# =========================================================
# ROI loading
# =========================================================
def load_rois():
    if not os.path.exists(ROIS_JSON_PATH):
        raise FileNotFoundError(f"ROIs not found: {ROIS_JSON_PATH} (run YOLO first)")

    with open(ROIS_JSON_PATH, "r", encoding="utf-8") as f:
        rois = json.load(f)

    if not isinstance(rois, list) or len(rois) == 0:
        raise RuntimeError(f"Invalid ROIs: {rois}")

    return rois


# =========================================================
# Main OCR logic
# =========================================================
def read_volume_trt(frame: np.ndarray, trt_model: TRTWrapper) -> int:
    rois = load_rois()

    # 위 -> 아래 정렬 (천/백/십/일)
    rois = sorted(rois, key=lambda r: r[1])

    h, w = frame.shape[:2]
    crops = []

    # ROI 4개만 사용 (나머지는 무시)
    for i, (x, y, rw, rh) in enumerate(rois[:4]):
        # clip to frame
        x1 = max(0, min(w - 1, int(x)))
        y1 = max(0, min(h - 1, int(y)))
        x2 = max(0, min(w, x1 + int(rw)))
        y2 = max(0, min(h, y1 + int(rh)))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            raise RuntimeError(f"Empty crop at ROI{i} (x1,y1,x2,y2={x1},{y1},{x2},{y2})")

        # 디버그 저장
        try:
            cv2.imwrite(f"/tmp/ocr_roi_{i}.jpg", crop)
        except Exception:
            pass

        crops.append(crop)

    if len(crops) < 4:
        raise RuntimeError(f"Not enough ROIs for OCR: {len(crops)} (need 4)")

    batch = np.stack([_preprocess_roi_bgr(c) for c in crops], axis=0).astype(np.float32)

    pred_cls, pred_conf, _ = trt_model.infer(batch)
    digits = [int(d) for d in pred_cls[:4]]

    volume = int(
        digits[0] * 1000 +
        digits[1] * 100 +
        digits[2] * 10 +
        digits[3]
    )
    return volume
