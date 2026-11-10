"""Export the downloaded YOLOv8 checkpoints to ONNX and write a manifest of their classes.

Usage: python tools/export_models.py <raw_dir> <out_dir>

Conversion only (no training). Each .pt has already been statically scanned with
tools/inspect_pickle.py; the only flagged global is ultralytics' getattr(Detect, 'forward').
"""
import hashlib
import json
import os
import shutil
import sys

from ultralytics import YOLO

MODELS = {
    "pothole": ("pothole_yolov8n_seg.pt", 640),
    "trash_turhancan": ("trash_turhancan_yolov8m_seg.pt", 640),
    "garbage_kendrickfff": ("garbage_kendrickfff_yolov8l.pt", 640),
    "coco": ("coco_yolov8n.pt", 640),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(raw_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    manifest = {}
    for key, (fname, imgsz) in MODELS.items():
        src = os.path.join(raw_dir, fname)
        print(f"== {key}: {fname}")
        model = YOLO(src)
        names = model.names
        task = model.task
        print(f"   task={task} classes={len(names)} -> {names if len(names) <= 20 else list(names.values())[:20]}")
        onnx_tmp = model.export(format="onnx", imgsz=imgsz, opset=17, simplify=True, dynamic=False, nms=False)
        dst = os.path.join(out_dir, f"{key}.onnx")
        shutil.move(onnx_tmp, dst)
        manifest[key] = {
            "source_file": fname,
            "source_sha256": sha256(src),
            "onnx": os.path.basename(dst),
            "onnx_sha256": sha256(dst),
            "onnx_mb": round(os.path.getsize(dst) / 1e6, 1),
            "task": task,
            "imgsz": imgsz,
            "names": {int(k): v for k, v in names.items()},
        }
    with open(os.path.join(out_dir, "models.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print("wrote", os.path.join(out_dir, "models.json"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
