from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image
from ultralytics import YOLO

FRUIT_CLASSES = {"apple", "banana", "orange"}
MODEL_NAME = "yolov8n.pt"
IMG_SIZE = 760
CONF_THRESHOLD = 0.15
IOU_THRESHOLD = 0.5

_model: YOLO | None = None
_supported: list[str] | None = None
_fruit_class_ids: list[int] | None = None


def load_model() -> YOLO:
    global _model
    if _model is None:
        _model = YOLO(MODEL_NAME)
    return _model


def get_supported_fruits(allow_load: bool = True) -> list[str]:
    global _supported
    if _supported is None:
        if not allow_load and _model is None:
            return []
        model = load_model()
        names = model.names or {}
        supported = {
            name.lower() for name in names.values() if name.lower() in FRUIT_CLASSES
        }
        _supported = sorted(supported)
    return _supported


def _get_fruit_class_ids() -> list[int]:
    global _fruit_class_ids
    if _fruit_class_ids is None:
        model = load_model()
        names = model.names or {}
        _fruit_class_ids = [
            int(cls_id)
            for cls_id, name in names.items()
            if str(name).lower() in FRUIT_CLASSES
        ]
    return _fruit_class_ids


def run_detection(image_path: Path) -> Tuple[Dict[str, int], int, Image.Image, int]:
    model = load_model()
    fruit_ids = _get_fruit_class_ids()
    start = time.perf_counter()
    if fruit_ids:
        results = model(
            str(image_path),
            imgsz=IMG_SIZE,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
            classes=fruit_ids,
        )
    else:
        results = model(
            str(image_path),
            imgsz=IMG_SIZE,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
        )
    processing_ms = int((time.perf_counter() - start) * 1000)

    result = results[0]
    names = result.names or {}
    counts: Dict[str, int] = {}

    if result.boxes is not None and result.boxes.cls is not None:
        for cls_id in result.boxes.cls.tolist():
            name = names.get(int(cls_id), "unknown")
            key = str(name).lower()
            if key in FRUIT_CLASSES:
                counts[key] = counts.get(key, 0) + 1

    total = sum(counts.values())

    plotted = result.plot()  # BGR numpy array
    image = Image.fromarray(plotted[..., ::-1])
    return counts, total, image, processing_ms
