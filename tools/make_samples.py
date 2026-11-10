"""Pick demo sample photos (staged/dataset images only, MIT-licensed) for the app's demo mode.

Runs the real decision pipeline over eval/set1 and copies one confident pothole, one confident
garbage pile, and one clean road (not_issue/uncertain) into app/assets/samples/, resized to 1024 px.
Usage: python tools/make_samples.py
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "api"))
from app.config import settings  # noqa: E402
from app.decide import decide  # noqa: E402
from app.vision import load_models, open_upright  # noqa: E402

OUT = os.path.join(ROOT, "app", "assets", "samples")
WANT = {"pothole": ("pothole", "issue"), "garbage": ("garbage", "issue"), "road": (None, "not_issue")}


def main():
    m = load_models(settings.model_dir, ["pothole", "trash_turhancan", "coco"], 2)
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "eval", "set1", "manifest.csv"))) if r["licence"] == "MIT"]
    best = {}
    for r in rows:
        kind = {"pothole": "pothole", "pothole_road": "pothole", "garbage": "garbage", "neg_road": "road"}.get(r["label"])
        if not kind:
            continue
        img = open_upright(os.path.join(ROOT, "eval", "set1", r["file"]))
        d = decide(img, m["pothole"](img), m["trash_turhancan"](img), m["coco"](img))
        cat, outcome = WANT[kind]
        ok = d.outcome == outcome and (cat is None or d.category == cat)
        score = d.confidence if cat else -d.confidence
        if ok and (kind not in best or score > best[kind][0]):
            best[kind] = (score, r, img, d)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "CREDITS.txt"), "w", encoding="utf-8") as cr:
        for kind, (score, r, img, d) in best.items():
            img = img.copy()
            img.thumbnail((1024, 1024))
            img.save(os.path.join(OUT, f"{kind}.jpg"), "JPEG", quality=85)
            cr.write(f"{kind}.jpg  <- {r['source']}  ({r['licence']})\n")
            print(kind, r["file"], d.outcome, d.category, round(d.confidence, 2))


if __name__ == "__main__":
    main()
