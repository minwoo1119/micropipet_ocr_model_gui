import json
import os
import numpy as np
import cv2
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit  # noqa

from worker.paths import OCR_TRT_PATH, ROIS_JSON_PATH

# 네 기존 설정값에 맞춤
INPUT_SIZE = (224, 224)
NORM_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
NORM_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
VOLUME_WEIGHTS = [1000, 100, 10, 1]


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

        # TensorRT 10: tensor name 기반
        self.input_name = self.engine.get_tensor_name(0)
        self.output_name = self.engine.get_tensor_name(1)

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


def _preprocess_roi_bgr(roi_bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, INPUT_SIZE, interpolation=cv2.INTER_LINEAR)
    x = resized.astype(np.float32) / 255.0
    x = (x - NORM_MEAN) / NORM_STD
    x = np.transpose(x, (2, 0, 1))  # CHW
    return x


def load_rois():
    if not os.path.exists(ROIS_JSON_PATH):
        raise FileNotFoundError(f"ROIs not found. Run YOLO first: {ROIS_JSON_PATH}")
    with open(ROIS_JSON_PATH, "r", encoding="utf-8") as f:
        rois = json.load(f)
    if not isinstance(rois, list) or len(rois) != 4:
        raise RuntimeError(f"Invalid ROIs (need 4). Got: {rois}")
    return rois


def read_volume_trt(frame: np.ndarray, trt_model: TRTWrapper) -> int:
    rois = load_rois()

    crops = []
    h, w = frame.shape[:2]
    for (x, y, rw, rh) in rois:
        x = max(0, min(w - 1, int(x)))
        y = max(0, min(h - 1, int(y)))
        rw = max(1, int(rw))
        rh = max(1, int(rh))
        crop = frame[y:y+rh, x:x+rw]
        if crop.size == 0:
            raise RuntimeError("Empty crop detected.")
        crops.append(crop)

    batch = np.stack([_preprocess_roi_bgr(c) for c in crops], axis=0).astype(np.float32)  # NCHW
    pred_cls, pred_conf, _ = trt_model.infer(batch)

    digits = [int(d) for d in pred_cls[:4]]
    volume = int(sum(digits[i] * VOLUME_WEIGHTS[i] for i in range(4)))
    return volume
