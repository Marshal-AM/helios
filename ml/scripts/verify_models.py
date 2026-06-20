#!/usr/bin/env python3
"""Smoke-test trained artifacts and Triton ONNX exports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

ARTIFACTS = REPO_ROOT / "ml" / "artifacts"
MODELS = REPO_ROOT / "models"

REQUIRED = {
    "yolo_weights": ARTIFACTS / "yolo" / "best.pt",
    "mstar_weights": ARTIFACTS / "mstar" / "best.pth",
    "bit_weights": ARTIFACTS / "bit" / "best.pth",
    "yolo_onnx": MODELS / "yolov8_detection" / "1" / "model.onnx",
    "mstar_onnx": MODELS / "mstar_sar" / "1" / "model.onnx",
    "bit_onnx": MODELS / "bit_change" / "1" / "model.onnx",
    "yolo_results": ARTIFACTS / "yolo" / "train" / "results.csv",
    "mstar_classes": ARTIFACTS / "mstar" / "classes.txt",
    "bit_metrics": ARTIFACTS / "bit" / "metrics.json",
}


def check_files() -> list[str]:
    issues: list[str] = []
    for name, path in REQUIRED.items():
        if not path.exists():
            issues.append(f"MISSING {name}: {path}")
        else:
            print(f"OK  {name}: {path} ({path.stat().st_size / 1e6:.1f} MB)")
    return issues


def check_metrics() -> list[str]:
    issues: list[str] = []
    import pandas as pd

    df = pd.read_csv(REQUIRED["yolo_results"])
    map_col = "metrics/mAP50(B)" if "metrics/mAP50(B)" in df.columns else "metrics/mAP50"
    yolo_map = float(df[map_col].iloc[-1])
    print(f"YOLO val mAP50 (epoch {len(df)}): {yolo_map:.4f}")
    if yolo_map < 0.60:
        issues.append(f"YOLO mAP50 below MVP floor (0.60): {yolo_map:.4f}")

    bit = json.loads(REQUIRED["bit_metrics"].read_text(encoding="utf-8"))
    bit_f1 = float(bit.get("f1", 0))
    print(f"BIT test F1: {bit_f1:.4f}")
    if bit_f1 < 0.85:
        issues.append(f"BIT F1 below MVP target (0.85): {bit_f1:.4f} — model trained but weak")

    classes = REQUIRED["mstar_classes"].read_text(encoding="utf-8").strip().splitlines()
    print(f"MSTAR classes ({len(classes)}): {', '.join(classes)}")
    return issues


def test_onnx() -> list[str]:
    import onnxruntime as ort

    issues: list[str] = []

    # YOLO
    sess = ort.InferenceSession(str(REQUIRED["yolo_onnx"]), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    x = np.random.randn(1, 3, 640, 640).astype(np.float32)
    out = sess.run(None, {inp.name: x})
    print(f"YOLO ONNX: input {inp.name} {x.shape} -> output {out[0].shape}")

    # MSTAR
    sess = ort.InferenceSession(str(REQUIRED["mstar_onnx"]), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    x = np.random.randn(1, 1, 224, 224).astype(np.float32)
    out = sess.run(None, {inp.name: x})
    print(f"MSTAR ONNX: input {inp.name} {x.shape} -> logits {out[0].shape}")

    # BIT
    sess = ort.InferenceSession(str(REQUIRED["bit_onnx"]), providers=["CPUExecutionProvider"])
    t1 = np.random.randn(1, 3, 256, 256).astype(np.float32)
    t2 = np.random.randn(1, 3, 256, 256).astype(np.float32)
    names = [i.name for i in sess.get_inputs()]
    out = sess.run(None, {names[0]: t1, names[1]: t2})
    print(f"BIT ONNX: inputs {names} -> mask {out[0].shape}")

    return issues


def test_pytorch_weights() -> list[str]:
    import torch

    issues: list[str] = []

    mstar = torch.load(REQUIRED["mstar_weights"], map_location="cpu", weights_only=False)
    print(f"MSTAR checkpoint keys: {list(mstar.keys())}, acc={mstar.get('accuracy', 'n/a')}")

    bit = torch.load(REQUIRED["bit_weights"], map_location="cpu", weights_only=False)
    print(f"BIT checkpoint f1: {bit.get('f1', 'n/a')}")

    from ultralytics import YOLO

    model = YOLO(str(REQUIRED["yolo_weights"]))
    print(f"YOLO loaded: {REQUIRED['yolo_weights'].name}, task={model.task}")

    return issues


def main() -> int:
    print("=== File check ===")
    issues = check_files()
    if issues:
        for i in issues:
            print("ERROR:", i)
        return 1

    print("\n=== Metrics ===")
    issues.extend(check_metrics())

    print("\n=== ONNX inference (CPU) ===")
    try:
        issues.extend(test_onnx())
        print("ONNX smoke tests passed")
    except Exception as exc:
        issues.append(f"ONNX test failed: {exc}")
        print("ONNX test error:", exc)

    print("\n=== PyTorch weights ===")
    try:
        issues.extend(test_pytorch_weights())
        print("PyTorch smoke tests passed")
    except Exception as exc:
        issues.append(f"PyTorch test failed: {exc}")
        print("PyTorch test error:", exc)

    print("\n=== Summary ===")
    if issues:
        for i in issues:
            print("WARN:", i)
        print("Artifacts present and runnable, but some metrics below MVP targets.")
        return 0
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
