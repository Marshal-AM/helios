# Helios ML Training Guide

Train models on **host WSL2 / Linux GPU VM** with CUDA. Docker runs Triton + inference workers only.

Use **Python 3.10 or 3.11** if possible (3.12 works with `requirements-train.txt`).

## Setup

```bash
cd /path/to/helios
python3 -m venv .venv-train
source .venv-train/bin/activate
pip install -U pip setuptools wheel
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r ml/requirements-train.txt
```

Add to `.env`:

```
KAGGLE_USERNAME=your-user
KAGGLE_KEY=your-key
ML_DATA_DIR=./ml/datasets
YOLO_MODEL_SIZE=s
```

## 1. Datasets

```bash
python ml/scripts/download_dota.py
python ml/scripts/convert_dota_obb.py

python ml/scripts/download_mstar_kaggle.py
python ml/scripts/download_levir_cd.py
python ml/scripts/download_whu_cd.py   # manual WHU files if needed
```

## 2. Training (VRAM-safe defaults)

| Model | Command | Output |
|-------|---------|--------|
| All three + export | `python ml/scripts/train_all.py` | `ml/artifacts/*` + `models/` ONNX |
| YOLOv8-OBB | `python ml/scripts/train_yolov8.py` | `ml/artifacts/yolo/best.pt` + 4 PNG charts |
| MSTAR CNN | `python ml/scripts/train_mstar.py` | `ml/artifacts/mstar/best.pth` + confusion matrix |
| BIT (simple) | `python ml/scripts/train_bit_simple.py` | `ml/artifacts/bit/best.pth` + metrics.json |
| BIT (open-cd, optional) | `python ml/scripts/train_bit.py` | needs `requirements-train-opencd.txt` |

Training takes hours on GPU. Charts must exist under `ml/artifacts/yolo/` before Phase 3 sign-off.

## 3. Export to Triton

```bash
python ml/scripts/export_triton.py
# Optional TensorRT (host with trtexec):
bash ml/scripts/export_tensorrt.sh
docker compose restart triton
```

Verify:

```bash
curl http://localhost:8000/v2/models/yolov8_detection/ready
curl http://localhost:8000/v2/models/mstar_sar/ready
curl http://localhost:8000/v2/models/bit_change/ready
```

## 4. End-to-end inference

After preprocessing produces tiles:

```powershell
docker compose exec inference-service celery -A helios_common.celery_app call inference_service.tasks.run_inference --args='[1, []]'
curl http://localhost:8080/detections/1/gradcam
```

## VRAM notes (3060 6GB)

- YOLO: `yolov8s-obb`, batch 4, FP16
- MSTAR: batch 16
- BIT: batch 2
- Triton serves ONNX by default; TensorRT optional via `export_tensorrt.sh`
