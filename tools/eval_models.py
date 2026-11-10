"""Run every model over the evaluation set, dump per-image features, and sweep thresholds.

Usage:
  python tools/eval_models.py <eval_dir> <model_dir> <out_csv>            # features + sweep
  python tools/eval_models.py <eval_dir> <model_dir> <out_csv> --parity   # also compare to ultralytics .pt

<eval_dir>/manifest.csv lists file,label. Synthetic blank images are generated into <eval_dir>/neg_blank.
"""
import csv
import os
import statistics as st
import sys
import time

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from app.vision import load_models, open_upright  # noqa: E402

ANIMALS = {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}
VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}


def make_blanks(eval_dir):
    d = os.path.join(eval_dir, "neg_blank")
    os.makedirs(d, exist_ok=True)
    rng = np.random.default_rng(0)
    imgs = {
        "grey.jpg": Image.new("RGB", (1024, 768), (128, 128, 128)),
        "white.jpg": Image.new("RGB", (1024, 768), (250, 250, 250)),
        "black.jpg": Image.new("RGB", (1024, 768), (5, 5, 5)),
        "gradient.jpg": Image.fromarray(np.tile(np.linspace(60, 200, 1024, dtype=np.uint8), (768, 1))).convert("RGB"),
        "lens_cap_noise.jpg": Image.fromarray((rng.normal(20, 6, (768, 1024))).clip(0, 255).astype(np.uint8)).convert("RGB"),
        "blurred_wall.jpg": Image.fromarray(rng.integers(150, 200, (96, 128, 3), dtype=np.uint8)).resize((1024, 768)).filter(ImageFilter.GaussianBlur(25)),
    }
    rows = []
    for name, im in imgs.items():
        im.save(os.path.join(d, name), quality=90)
        rows.append({"file": f"neg_blank/{name}", "label": "neg_blank"})
    return rows


def gray_std(img):
    g = np.asarray(img.convert("L").resize((256, 256)), dtype=np.float32)
    return float(g.std())


def features(models, img):
    f = {"gray_std": round(gray_std(img), 2)}
    t = {}
    for key, m in models.items():
        t0 = time.perf_counter()
        r = m(img, conf=0.10)
        t[key] = time.perf_counter() - t0
        dets = r.detections
        if key == "coco":
            person = [d for d in dets if d.name == "person"]
            f["person_max"] = round(max((d.conf for d in person), default=0), 3)
            f["person_box"] = round(max(((d.box[2] - d.box[0]) * (d.box[3] - d.box[1]) for d in person if d.conf >= 0.4), default=0), 3)
            f["animal_max"] = round(max((d.conf for d in dets if d.name in ANIMALS), default=0), 3)
            f["animal_box"] = round(max(((d.box[2] - d.box[0]) * (d.box[3] - d.box[1]) for d in dets if d.name in ANIMALS and d.conf >= 0.4), default=0), 3)
            f["vehicle_max"] = round(max((d.conf for d in dets if d.name in VEHICLES), default=0), 3)
        else:
            f[f"{key}_max"] = round(r.max_conf, 3)
            f[f"{key}_n25"] = sum(d.conf >= 0.25 for d in dets)
            f[f"{key}_n40"] = sum(d.conf >= 0.40 for d in dets)
            if m.task == "segment":
                f[f"{key}_area"] = round(r.mask_area, 4)
                f[f"{key}_area40"] = round(sum(d.area for d in dets if d.conf >= 0.40), 4)
    return f, t


def sweep(rows, positive, score_key, thresholds):
    print(f"\n-- {positive.upper()} via {score_key}: threshold, precision, recall, FP labels")
    for th in thresholds:
        tp = sum(1 for r in rows if r["label"] == positive and float(r[score_key]) >= th)
        fp_rows = [r for r in rows if r["label"] != positive and float(r[score_key]) >= th]
        fn = sum(1 for r in rows if r["label"] == positive and float(r[score_key]) < th)
        p = tp / (tp + len(fp_rows)) if tp + len(fp_rows) else 0
        rec = tp / (tp + fn) if tp + fn else 0
        fpl = {}
        for r in fp_rows:
            fpl[r["label"]] = fpl.get(r["label"], 0) + 1
        print(f"   {th:>5}  P={p:.2f}  R={rec:.2f}  FP={fpl}")


def parity(eval_dir, rows, model_dir):
    from ultralytics import YOLO
    raw = os.path.join(model_dir, "raw")
    pairs = {"pothole": "pothole_yolov8n_seg.pt", "trash_turhancan": "trash_turhancan_yolov8m_seg.pt"}
    ours = load_models(model_dir, list(pairs))
    print("\n-- PARITY (max conf) ours-onnx vs ultralytics-onnx (same graph: tests post-processing),")
    print("   and ours-onnx vs ultralytics-.pt (rect letterbox: tests input-shape sensitivity)")
    for key, pt in pairs.items():
        ref_onnx = YOLO(os.path.join(model_dir, f"{key}.onnx"), task=ours[key].task)
        ref_pt = YOLO(os.path.join(raw, pt))
        d_onnx, d_pt = [], []
        for r in rows[::3]:
            img = open_upright(os.path.join(eval_dir, r["file"]))
            # pre-shrink to 640 so both pipelines see identical pixels (isolates post-processing)
            img.thumbnail((640, 640))
            mx = lambda res: float(res.boxes.conf.max()) if len(res.boxes) else 0.0  # noqa: E731
            a = mx(ref_onnx.predict(img, imgsz=640, conf=0.10, verbose=False)[0])
            p = mx(ref_pt.predict(img, imgsz=640, conf=0.10, verbose=False)[0])
            b = ours[key](img, conf=0.10).max_conf
            d_onnx.append(abs(a - b))
            d_pt.append(abs(p - b))
        print(f"   {key}: n={len(d_onnx)} vs-onnx mean={st.mean(d_onnx):.4f} max={max(d_onnx):.4f} | "
              f"vs-pt mean={st.mean(d_pt):.4f} max={max(d_pt):.4f}")


def main(eval_dir, model_dir, out_csv, do_parity):
    with open(os.path.join(eval_dir, "manifest.csv"), encoding="utf-8") as fh:
        rows = [{"file": r["file"], "label": r["label"]} for r in csv.DictReader(fh)]
    rows += make_blanks(eval_dir)
    models = load_models(model_dir)
    times = {k: [] for k in models}
    out = []
    for r in rows:
        img = open_upright(os.path.join(eval_dir, r["file"]))
        f, t = features(models, img)
        for k, v in t.items():
            times[k].append(v)
        out.append({**r, **f})
    keys = list(out[0].keys())
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {out_csv} ({len(out)} images)")
    print("\nlatency per image (median s):", {k: round(st.median(v), 3) for k, v in times.items()})

    labels = sorted({r["label"] for r in out})
    print("\nmedian feature per label:")
    for k in keys[2:]:
        print(f"  {k:<26}" + "  ".join(f"{lab}={st.median(float(r[k]) for r in out if r['label'] == lab):.3f}" for lab in labels))

    sweep(out, "pothole", "pothole_max", [0.25, 0.35, 0.5, 0.6, 0.7])
    sweep(out, "garbage", "trash_turhancan_max", [0.25, 0.4, 0.5, 0.6, 0.7])
    sweep(out, "garbage", "trash_turhancan_area", [0.01, 0.03, 0.05, 0.1])
    sweep(out, "garbage", "trash_turhancan_n40", [1, 2, 3, 5])
    sweep(out, "garbage", "garbage_kendrickfff_max", [0.25, 0.4, 0.5, 0.6, 0.7])
    sweep(out, "garbage", "garbage_kendrickfff_n40", [1, 2, 3, 5])
    if do_parity:
        parity(eval_dir, rows, model_dir)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], "--parity" in sys.argv)
