"""Score the end-to-end decision logic (api/app/decide.py) on the evaluation set.

Usage: python tools/eval_decisions.py <eval_dir> <model_dir>
Prints an outcome table per true label and the judge-relevant numbers:
 - irrelevant images (blank/person/animal/street/road) that would be suggested as an issue
 - issue images that got the right suggestion (issue or uncertain with the right category)
"""
import csv
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from app.decide import decide  # noqa: E402
from app.vision import load_models, open_upright  # noqa: E402


def main(eval_dir, model_dir):
    with open(os.path.join(eval_dir, "manifest.csv"), encoding="utf-8") as fh:
        rows = [(r["file"], r["label"]) for r in csv.DictReader(fh)]
    override_path = os.path.join(eval_dir, "labels_override.csv")
    if os.path.exists(override_path):  # manual relabels after visual review
        with open(override_path, encoding="utf-8") as fh:
            ov = {r["file"]: r["label"] for r in csv.DictReader(fh)}
        rows = [(f, ov.get(f, label)) for f, label in rows]
    blank_dir = os.path.join(eval_dir, "neg_blank")
    if os.path.isdir(blank_dir):
        rows += [(f"neg_blank/{f}", "neg_blank") for f in os.listdir(blank_dir)]
    models = load_models(model_dir, ["pothole", "trash_turhancan", "coco"])
    table = defaultdict(Counter)
    misses = []
    for f, label in rows:
        img = open_upright(os.path.join(eval_dir, f))
        d = decide(img, models["pothole"](img), models["trash_turhancan"](img), models["coco"](img))
        key = d.outcome if d.outcome == "not_issue" else f"{d.outcome}:{d.category}"
        table[label][key] += 1
        expected = label if label in ("pothole", "garbage") else None
        if label == "litter_single":  # one item: not "accumulation"; any outcome but pothole is fine
            wrong = d.category == "pothole" and d.outcome == "issue"
        else:
            wrong = (expected and not (d.outcome in ("issue", "uncertain") and d.category == expected)) or \
                    (not expected and d.outcome == "issue")
        if wrong:
            misses.append((f, label, key, d.reason, d.scores))
    cols = ["issue:pothole", "issue:garbage", "uncertain:pothole", "uncertain:garbage", "not_issue"]
    print(f"{'label':<12}" + "".join(f"{c:>19}" for c in cols))
    for label in sorted(table):
        print(f"{label:<12}" + "".join(f"{table[label][c]:>19}" for c in cols))
    neg = [lab for lab in table if lab.startswith("neg_")]
    n_neg = sum(sum(table[lab].values()) for lab in neg)
    neg_issue = sum(table[lab]["issue:pothole"] + table[lab]["issue:garbage"] for lab in neg)
    print(f"\nirrelevant images confidently suggested as an issue: {neg_issue}/{n_neg}")
    for cat in ("pothole", "garbage"):
        n = sum(table[cat].values())
        ok = table[cat][f"issue:{cat}"] + table[cat][f"uncertain:{cat}"]
        conf = table[cat][f"issue:{cat}"]
        print(f"{cat}: right category suggested {ok}/{n} (confident {conf}/{n})")
    print("\nmisses:")
    for m in misses:
        print("  ", m)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
