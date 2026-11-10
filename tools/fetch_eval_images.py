"""Download a small, licence-tracked evaluation set from Wikimedia Commons.

Usage: python -I tools/fetch_eval_images.py <out_dir>

Every image lands in <out_dir>/<label>/ and is recorded in <out_dir>/manifest.csv
with its source page, author and licence, so the demo set is attributable.
Labels: pothole, garbage, neg_person, neg_animal, neg_vehicle.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "RaastaAI-eval/0.1 (hackathon evaluation set; contact via project repo)"
API = "https://commons.wikimedia.org/w/api.php"

CATEGORIES = {
    "pothole": ["Category:Potholes", "Category:Potholes in India", "Category:Potholes in Pakistan", "Category:Road damage"],
    "garbage": ["Category:Garbage in India", "Category:Garbage in Pakistan", "Category:Litter in India",
                "Category:Illegal dumping", "Category:Garbage dumps", "Category:Litter on roads"],
    "neg_person": ["Category:Pedestrians", "Category:People walking"],
    "neg_animal": ["Category:Stray dogs", "Category:Cats lying down", "Category:Cows on roads"],
    "neg_vehicle": ["Category:Auto rickshaws in Pakistan", "Category:Cars in Lahore", "Category:Traffic in Lahore"],
}
TARGET = {"pothole": 14, "garbage": 14, "neg_person": 5, "neg_animal": 5, "neg_vehicle": 5}
ALLOWED_LICENCE = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? [0-9.]+)", re.I)


def get(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def category_files(cat, limit=50):
    data = json.loads(get(API, {
        "action": "query", "format": "json", "generator": "categorymembers",
        "gcmtitle": cat, "gcmtype": "file", "gcmlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 1280,
    }))
    pages = (data.get("query") or {}).get("pages") or {}
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata") or {}
        lic = strip_html((meta.get("LicenseShortName") or {}).get("value"))
        if not ALLOWED_LICENCE.match(lic):
            continue
        yield {
            "title": p["title"],
            "thumb": info.get("thumburl") or info.get("url"),
            "page": info.get("descriptionurl"),
            "author": strip_html((meta.get("Artist") or {}).get("value"))[:120],
            "licence": lic,
        }


def main(out):
    os.makedirs(out, exist_ok=True)
    rows = []
    for label, cats in CATEGORIES.items():
        os.makedirs(os.path.join(out, label), exist_ok=True)
        got = 0
        seen = set()
        for cat in cats:
            if got >= TARGET[label]:
                break
            try:
                files = list(category_files(cat))
            except Exception as e:  # category missing or API hiccup
                print(f"  skip {cat}: {e}")
                continue
            print(f"{label}: {cat} -> {len(files)} candidates")
            for f in files:
                if got >= TARGET[label] or f["title"] in seen:
                    continue
                seen.add(f["title"])
                name = f"{label}_{got + 1:02d}.jpg"
                try:
                    blob = get(f["thumb"])
                except Exception as e:
                    print(f"  fail {f['title']}: {e}")
                    continue
                with open(os.path.join(out, label, name), "wb") as fh:
                    fh.write(blob)
                rows.append({"file": f"{label}/{name}", "label": label, **f})
                got += 1
                time.sleep(0.3)
        print(f"== {label}: {got}/{TARGET[label]}")
    with open(os.path.join(out, "manifest.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "label", "title", "page", "author", "licence", "thumb"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} images")


if __name__ == "__main__":
    main(sys.argv[1])
