"""ONNX Runtime inference for YOLOv8 detect / segment models, numpy-only post-processing.

No torch or ultralytics at runtime: keeps the API image small and cold starts fast.
Mirrors ultralytics' letterbox -> NMS -> mask pipeline closely enough for decisions
(parity is checked by tools/eval_models.py --parity).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

PAD_VALUE = 114


def open_upright(src) -> Image.Image:
    """Open an image (path or file-like) and apply its EXIF orientation, so phone photos
    are not fed to the models sideways. Returns RGB."""
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


@dataclass
class Detection:
    cls: int
    name: str
    conf: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 as fractions of the original image
    area: float = 0.0  # mask area as a fraction of the image (segment models only)


@dataclass
class Result:
    model: str
    detections: list[Detection] = field(default_factory=list)
    mask_area: float = 0.0  # union of all masks, fraction of the image (segment models only)

    @property
    def max_conf(self) -> float:
        return max((d.conf for d in self.detections), default=0.0)


def letterbox(img: Image.Image, size: int):
    """Resize keeping aspect ratio and pad to size x size (ultralytics LetterBox geometry).

    Downscaling uses INTER_AREA (antialiased): phone photos are 3-12 MP while the models were
    trained on ~640 px dataset images, and plain INTER_LINEAR aliasing measurably lowered
    pothole recall on our eval set. Upscaling uses INTER_LINEAR like ultralytics."""
    w, h = img.size
    r = min(size / h, size / w)
    nw, nh = int(round(w * r)), int(round(h * r))
    dw, dh = (size - nw) / 2, (size - nh) / 2
    left, top = int(round(dw - 0.1)), int(round(dh - 0.1))
    arr = np.asarray(img, dtype=np.uint8)
    if (nw, nh) != (w, h):
        interp = cv2.INTER_AREA if r < 1 else cv2.INTER_LINEAR
        arr = cv2.resize(arr, (nw, nh), interpolation=interp)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    canvas[top:top + nh, left:left + nw] = arr
    x = canvas.astype(np.float32) / 255.0
    x = np.ascontiguousarray(x.transpose(2, 0, 1)[None])
    return x, r, left, top, nw, nh


def nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> list[int]:
    order = scores.argsort()[::-1]
    keep = []
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1).clip(0) * (y2 - y1).clip(0)
    while order.size:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = (xx2 - xx1).clip(0) * (yy2 - yy1).clip(0)
        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][ovr <= iou]
    return keep


class YoloOnnx:
    def __init__(self, path: str, names: dict[int, str], task: str, imgsz: int = 640, threads: int = 2):
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
        self.input = self.sess.get_inputs()[0].name
        self.names = names
        self.nc = len(names)
        self.task = task
        self.imgsz = imgsz
        self.key = os.path.splitext(os.path.basename(path))[0]

    def __call__(self, img: Image.Image, conf: float = 0.10, iou: float = 0.7, max_det: int = 100) -> Result:
        img = img.convert("RGB")
        W, H = img.size
        x, r, left, top, nw, nh = letterbox(img, self.imgsz)
        outs = self.sess.run(None, {self.input: x})
        pred = outs[0][0].T  # (8400, 4 + nc [+ 32])
        scores_all = pred[:, 4:4 + self.nc]
        cls = scores_all.argmax(1)
        scores = scores_all[np.arange(len(cls)), cls]
        m = scores >= conf
        if not m.any():
            return Result(self.key)
        pred, cls, scores = pred[m], cls[m], scores[m]
        xy, wh = pred[:, :2], pred[:, 2:4]
        boxes = np.concatenate([xy - wh / 2, xy + wh / 2], 1)  # letterbox pixel space
        offset = cls[:, None].astype(np.float32) * 7680.0  # class-aware NMS
        keep = nms(boxes + offset, scores, iou)[:max_det]
        boxes, cls, scores = boxes[keep], cls[keep], scores[keep]

        res = Result(self.key)
        union = None
        if self.task == "segment" and len(outs) > 1:
            protos = outs[1][0]  # (32, ph, pw)
            ph, pw = protos.shape[1:]
            coeffs = pred[keep, 4 + self.nc:]
            masks = 1 / (1 + np.exp(-(coeffs @ protos.reshape(len(protos), -1))))
            masks = masks.reshape(-1, ph, pw)
            sx, sy = pw / self.imgsz, ph / self.imgsz
            # content region (exclude padding) in proto space
            cx1, cy1 = int(left * sx), int(top * sy)
            cx2, cy2 = int(np.ceil((left + nw) * sx)), int(np.ceil((top + nh) * sy))
            content = max(1, (cx2 - cx1) * (cy2 - cy1))
            union = np.zeros((ph, pw), dtype=bool)
            areas = []
            for k, b in enumerate(boxes):
                bx1, by1 = int(max(cx1, b[0] * sx)), int(max(cy1, b[1] * sy))
                bx2, by2 = int(min(cx2, np.ceil(b[2] * sx))), int(min(cy2, np.ceil(b[3] * sy)))
                mk = np.zeros((ph, pw), dtype=bool)
                mk[by1:by2, bx1:bx2] = masks[k, by1:by2, bx1:bx2] > 0.5
                areas.append(mk.sum() / content)
                union |= mk
            res.mask_area = float(union.sum() / content)
        else:
            areas = [0.0] * len(boxes)

        for k, b in enumerate(boxes):
            x1 = float(np.clip((b[0] - left) / r / W, 0, 1))
            y1 = float(np.clip((b[1] - top) / r / H, 0, 1))
            x2 = float(np.clip((b[2] - left) / r / W, 0, 1))
            y2 = float(np.clip((b[3] - top) / r / H, 0, 1))
            c = int(cls[k])
            res.detections.append(Detection(c, self.names[c], float(scores[k]), (x1, y1, x2, y2), float(areas[k])))
        return res


def load_models(model_dir: str, keys: list[str] | None = None, threads: int = 2) -> dict[str, YoloOnnx]:
    with open(os.path.join(model_dir, "models.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    out = {}
    for key, m in manifest.items():
        if keys and key not in keys:
            continue
        names = {int(k): v for k, v in m["names"].items()}
        out[key] = YoloOnnx(os.path.join(model_dir, m["onnx"]), names, m["task"], m["imgsz"], threads)
    return out
