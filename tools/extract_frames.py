"""Extract evenly spaced frames from a video into an eval folder and append them to manifest.csv.

Usage: python tools/extract_frames.py <video> <eval_dir> <label> <n> <source_note> <licence>
"""
import csv
import os
import sys

import cv2


def main(video, eval_dir, label, n, source, licence):
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_dir = os.path.join(eval_dir, label)
    os.makedirs(out_dir, exist_ok=True)
    existing = len([f for f in os.listdir(out_dir) if f.endswith(".jpg")])
    rows = []
    for i in range(n):
        idx = int((i + 0.5) * total / n)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        name = f"{label}_{existing + len(rows) + 1:02d}.jpg"
        cv2.imwrite(os.path.join(out_dir, name), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        rows.append({"file": f"{label}/{name}", "label": label, "source": f"{source}#frame{idx}", "licence": licence, "boxes": ""})
    path = os.path.join(eval_dir, "manifest.csv")
    with open(path, "a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=["file", "label", "source", "licence", "boxes"]).writerows(rows)
    print(f"{total} frames in video; wrote {len(rows)} to {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6])
