"""Build the licence-tracked evaluation set from public Hugging Face datasets.

Usage: python -I tools/fetch_eval_hf.py <out_dir>

Sources (all fetched as raw files from the Hub; nothing here is used for training):
  pothole     Arpitraj01/Pothole_classification  datasets/test/<pothole class>   MIT
  neg_road    Arpitraj01/Pothole_classification  datasets/test/<normal class>    MIT
  garbage     Shynuaa/Street-garbage  yolo/test   images whose label file has >= 1 box   MIT
  neg_street  Shynuaa/Street-garbage  yolo/test   clean scenes (empty label file)        MIT
  garbage     Akhila-9849/Garbage_Bin_overflow_images (overflowing bins)                 CC-BY-4.0
  neg_person  ultralytics/assets release images (people, bus)                            AGPL-3.0
  neg_animal  datasets-server rows of microsoft/cats_vs_dogs (best effort)
Writes <out_dir>/<label>/*.jpg and <out_dir>/manifest.csv (file, label, source, licence, boxes).
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = "RaastaAI-eval/0.1"
HUB = "https://huggingface.co"


def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def tree(ds, path):
    return json.loads(http(f"{HUB}/api/datasets/{ds}/tree/main/{urllib.parse.quote(path)}"))


def raw(ds, path):
    return http(f"{HUB}/datasets/{ds}/resolve/main/{urllib.parse.quote(path)}")


def spread(items, n):
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


class Out:
    def __init__(self, root):
        self.root = root
        self.rows = []
        self.count = {}

    def save(self, label, blob, source, licence, boxes=""):
        os.makedirs(os.path.join(self.root, label), exist_ok=True)
        self.count[label] = self.count.get(label, 0) + 1
        name = f"{label}_{self.count[label]:02d}.jpg"
        with open(os.path.join(self.root, label, name), "wb") as fh:
            fh.write(blob)
        self.rows.append({"file": f"{label}/{name}", "label": label, "source": source, "licence": licence, "boxes": boxes})

    def write(self):
        with open(os.path.join(self.root, "manifest.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["file", "label", "source", "licence", "boxes"])
            w.writeheader()
            w.writerows(self.rows)
        print("counts:", self.count, "total:", len(self.rows))


def potholes(out):
    ds = "Arpitraj01/Pothole_classification"
    classes = [e["path"] for e in tree(ds, "datasets/test") if e["type"] == "directory"]
    print("pothole classes:", classes)
    for cdir in classes:
        cname = cdir.rsplit("/", 1)[-1].lower()
        # classes are severities (low/medium/severe) plus 'none' = clean road
        label = "neg_road" if cname in ("none", "normal", "plain") else "pothole"
        files = [e["path"] for e in tree(ds, cdir) if e["type"] == "file" and e["path"].lower().endswith((".jpg", ".jpeg", ".png"))]
        for p in spread(files, 5 if label == "pothole" else 8):
            out.save(label, raw(ds, p), f"{ds}:{p}", "MIT")
            time.sleep(0.1)


def street_garbage(out):
    ds = "Shynuaa/Street-garbage"
    imgs = [e["path"] for e in tree(ds, "yolo/test/images") if e["type"] == "file"]
    labels = {e["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0]: e for e in tree(ds, "yolo/test/labels") if e["type"] == "file"}
    want = {"garbage": 12, "neg_street": 6}
    got = {"garbage": 0, "neg_street": 0}
    for p in spread(imgs, len(imgs)):
        stem = p.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        lab = labels.get(stem)
        nboxes = 0
        if lab and lab.get("size", 0) > 0:
            nboxes = len([l for l in raw(ds, lab["path"]).decode().splitlines() if l.strip()])
        label = "garbage" if nboxes > 0 else "neg_street"
        if got[label] >= want[label]:
            continue
        out.save(label, raw(ds, p), f"{ds}:{p}", "MIT", str(nboxes))
        got[label] += 1
        if got == want:
            break
        time.sleep(0.1)


def bins(out):
    ds = "Akhila-9849/Garbage_Bin_overflow_images"
    files = [e["path"] for e in tree(ds, "") if e["type"] == "file" and e["path"].lower().endswith(".jpg")]
    for p in spread(files, 4):
        out.save("garbage", raw(ds, p), f"{ds}:{p}", "CC-BY-4.0")


def people(out):
    for name in ("bus.jpg", "zidane.jpg"):
        out.save("neg_person", http(f"https://github.com/ultralytics/assets/releases/download/v0.0.0/{name}"),
                 f"ultralytics/assets:{name}", "AGPL-3.0")


def animals(out):
    try:
        url = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(
            {"dataset": "microsoft/cats_vs_dogs", "config": "default", "split": "train", "offset": 0, "length": 40})
        rows = json.loads(http(url))["rows"]
        for item in spread(rows, 6):
            img = item["row"].get("image") or {}
            if img.get("src"):
                out.save("neg_animal", http(img["src"]), f"microsoft/cats_vs_dogs:row{item['row_idx']}", "see dataset card")
    except Exception as e:
        print("animals skipped:", e)


def main(root):
    out = Out(root)
    for step in (potholes, street_garbage, bins, people, animals):
        try:
            step(out)
        except Exception as e:
            print(f"{step.__name__} failed: {e}")
    out.write()


if __name__ == "__main__":
    main(sys.argv[1])
