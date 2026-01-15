#!/usr/bin/env python3
import argparse
import numpy as np
import cv2
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit  # noqa: F401


TRT_LOGGER = trt.Logger(trt.Logger.INFO)


def load_engine(engine_path: str) -> trt.ICudaEngine:
    with open(engine_path, "rb") as f, trt.Runtime(TRT_LOGGER) as runtime:
        engine = runtime.deserialize_cuda_engine(f.read())
    if engine is None:
        raise RuntimeError(f"Failed to load engine: {engine_path}")
    return engine


def engine_summary(engine: trt.ICudaEngine, name: str):
    print(f"\n========== ENGINE SUMMARY: {name} ==========")
    print("num_io_tensors:", engine.num_io_tensors)

    # IO tensor info
    for i in range(engine.num_io_tensors):
        tname = engine.get_tensor_name(i)
        mode = engine.get_tensor_mode(tname)
        dtype = engine.get_tensor_dtype(tname)
        shape = engine.get_tensor_shape(tname)
        print(f"\n[TENSOR {i}]")
        print(" name :", tname)
        print(" mode :", mode)
        print(" dtype:", dtype)
        print(" shape:", tuple(shape))

    # Optimization profiles (dynamic) info
    print("\n-- Optimization Profiles --")
    try:
        nprof = engine.num_optimization_profiles
        print("num_optimization_profiles:", nprof)
        for p in range(nprof):
            print(f" [profile {p}]")
            for i in range(engine.num_io_tensors):
                tname = engine.get_tensor_name(i)
                if engine.get_tensor_mode(tname) != trt.TensorIOMode.INPUT:
                    continue
                min_s, opt_s, max_s = engine.get_tensor_profile_shape(tname, p)
                print(f"   input={tname} min={tuple(min_s)} opt={tuple(opt_s)} max={tuple(max_s)}")
    except Exception as e:
        print("profile info not available:", e)


def preprocess_image(img_path: str, img_size: int = 224) -> np.ndarray:
    """
    IMPORTANT:
    - 이 전처리는 "일반적인 EfficientNet(ImageNet mean/std)" 가정.
    - 프로젝트의 실제 전처리와 다르면 결과 비교가 왜곡될 수 있음.
    - 그래도 '두 엔진이 같은 입력에서 어떻게 달라지는지' 비교에는 유효.
    """
    bgr = cv2.imread(img_path)
    if bgr is None:
        raise FileNotFoundError(img_path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (img_size, img_size), interpolation=cv2.INTER_LINEAR)
    x = rgb.astype(np.float32) / 255.0

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    x = (x - mean) / std

    # NCHW
    x = np.transpose(x, (2, 0, 1))
    x = np.expand_dims(x, axis=0)
    return np.ascontiguousarray(x)


def allocate_io(context: trt.IExecutionContext, engine: trt.ICudaEngine, batch_input: np.ndarray):
    # find first input / output
    input_names = []
    output_names = []
    for i in range(engine.num_io_tensors):
        tname = engine.get_tensor_name(i)
        if engine.get_tensor_mode(tname) == trt.TensorIOMode.INPUT:
            input_names.append(tname)
        else:
            output_names.append(tname)

    if len(input_names) != 1 or len(output_names) != 1:
        raise RuntimeError(f"Expected 1 input & 1 output, got {len(input_names)} / {len(output_names)}")

    in_name = input_names[0]
    out_name = output_names[0]

    # set input shape for dynamic engines
    context.set_input_shape(in_name, batch_input.shape)

    out_shape = tuple(context.get_tensor_shape(out_name))
    if -1 in out_shape:
        # sometimes output remains dynamic until shapes fully specified
        out_shape = tuple(engine.get_tensor_shape(out_name))
    if -1 in out_shape:
        raise RuntimeError(f"Output shape unresolved: {out_shape}")

    # allocate
    d_in = cuda.mem_alloc(batch_input.nbytes)
    out_nbytes = np.prod(out_shape) * np.dtype(np.float32).itemsize
    d_out = cuda.mem_alloc(int(out_nbytes))

    return in_name, out_name, out_shape, d_in, d_out


def run_infer(engine_path: str, img_path: str, profile_index: int = 0):
    engine = load_engine(engine_path)
    engine_name = engine_path
    engine_summary(engine, engine_name)

    context = engine.create_execution_context()
    if context is None:
        raise RuntimeError("Failed to create context")

    # select profile if multiple
    try:
        if engine.num_optimization_profiles > 1:
            context.set_optimization_profile_async(profile_index, cuda.Stream().handle)
    except Exception:
        pass

    x = preprocess_image(img_path, img_size=224)

    in_name, out_name, out_shape, d_in, d_out = allocate_io(context, engine, x)

    stream = cuda.Stream()

    # bind addresses
    context.set_tensor_address(in_name, int(d_in))
    context.set_tensor_address(out_name, int(d_out))

    # H2D
    cuda.memcpy_htod_async(d_in, x, stream)

    # execute
    ok = context.execute_async_v3(stream.handle)
    if not ok:
        raise RuntimeError("execute_async_v3 failed")

    # D2H
    y = np.empty(out_shape, dtype=np.float32)
    cuda.memcpy_dtoh_async(y, d_out, stream)
    stream.synchronize()

    y1 = y.reshape(-1)

    stats = {
        "min": float(y1.min()),
        "max": float(y1.max()),
        "sum": float(y1.sum()),
        "argmax": int(np.argmax(y1)),
    }
    return y1, stats


def softmax(x):
    x = x.astype(np.float64)
    x = x - np.max(x)
    e = np.exp(x)
    return (e / np.sum(e)).astype(np.float64)


def compare_outputs(y_old: np.ndarray, y_new: np.ndarray):
    assert y_old.shape == y_new.shape
    l1 = float(np.mean(np.abs(y_old - y_new)))
    l2 = float(np.sqrt(np.mean((y_old - y_new) ** 2)))
    corr = float(np.corrcoef(y_old, y_new)[0, 1])

    # logits vs prob 추정
    old_is_prob = (y_old.min() >= -1e-4) and (y_old.max() <= 1.0 + 1e-4) and (abs(y_old.sum() - 1.0) < 1e-2)
    new_is_prob = (y_new.min() >= -1e-4) and (y_new.max() <= 1.0 + 1e-4) and (abs(y_new.sum() - 1.0) < 1e-2)

    return {
        "L1_mean_abs_diff": l1,
        "L2_rmse": l2,
        "corrcoef": corr,
        "old_looks_like_prob": old_is_prob,
        "new_looks_like_prob": new_is_prob,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="old engine path (known good)")
    ap.add_argument("--new", required=True, help="new engine path (suspect)")
    ap.add_argument("--img", required=True, help="test ROI image path")
    args = ap.parse_args()

    y_old, st_old = run_infer(args.old, args.img)
    y_new, st_new = run_infer(args.new, args.img)

    print("\n========== INFERENCE STATS ==========")
    print("[OLD]", st_old)
    print("[NEW]", st_new)

    print("\n========== RAW OUTPUT ==========")
    print("OLD:", y_old)
    print("NEW:", y_new)

    cmp = compare_outputs(y_old, y_new)
    print("\n========== COMPARE ==========")
    for k, v in cmp.items():
        print(f"{k}: {v}")

    # softmax 비교(둘 다 logits일 때 특히 유용)
    sm_old = softmax(y_old)
    sm_new = softmax(y_new)
    print("\n========== SOFTMAX (computed) ==========")
    print("OLD softmax sum:", float(sm_old.sum()), "argmax:", int(np.argmax(sm_old)), "vals:", sm_old)
    print("NEW softmax sum:", float(sm_new.sum()), "argmax:", int(np.argmax(sm_new)), "vals:", sm_new)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
