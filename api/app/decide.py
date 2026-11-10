"""Turn raw model outputs into the user-facing outcome: issue / uncertain / not_issue.

The AI only *suggests*: every outcome still requires the citizen to confirm or pick a category.
Thresholds come from tools/eval_models.py on eval/set1 (see docs/MODEL_EVAL.md); keep them here,
in one place, so the API, tests and docs agree.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
from PIL import Image

from .vision import Result

# --- calibrated thresholds -------------------------------------------------------------------
BLANK_STD = 8.0            # grayscale std-dev below this = blank / lens cap / uniform wall
GATE_CONF = 0.40           # COCO confidence for a person/animal to count
GATE_BOX = 0.15            # ...and it must cover >= 15% of the image to be "the subject"
GATE_GROUP_N = 3           # or a group: >= 3 people...
GATE_GROUP_AREA = 0.25     # ...covering >= 25% of the image together
CONFLICT_GARBAGE = 0.45    # a litter item this confident next to a "pothole" -> ask the user
POTHOLE_ISSUE = 0.50       # pothole max conf for a confident suggestion
POTHOLE_UNSURE = 0.25      # below this the pothole model is ignored
GARBAGE_DET_CONF = 0.40    # a trash-model detection counts at this confidence
GARBAGE_MIN_DETS = 2       # accumulation = several items...
GARBAGE_MIN_AREA = 0.03    # ...or litter covering >= 3% of the image
GARBAGE_ISSUE = 0.50       # and the strongest item must be at least this confident
GARBAGE_UNSURE = 0.40      # a single item / weaker evidence -> uncertain

ANIMALS = {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}


@dataclass
class Decision:
    outcome: str                      # issue | uncertain | not_issue
    category: str | None              # pothole | garbage | None (suggestion only)
    confidence: float                 # 0..1, the score behind the suggestion
    reason: str                       # short machine-readable reason
    scores: dict = field(default_factory=dict)
    boxes: list = field(default_factory=list)  # [{cls, conf, box}] for the overlay

    def to_dict(self):
        return asdict(self)


def gray_std(img: Image.Image) -> float:
    g = np.asarray(img.convert("L").resize((256, 256)), dtype=np.float32)
    return float(g.std())


def _largest(dets, names, conf):
    return max(((d.box[2] - d.box[0]) * (d.box[3] - d.box[1]) for d in dets if d.name in names and d.conf >= conf), default=0.0)


def decide(img: Image.Image, pothole: Result | None, trash: Result | None, coco: Result | None) -> Decision:
    std = gray_std(img)
    if std < BLANK_STD:
        return Decision("not_issue", None, 0.0, "blank_image", {"gray_std": round(std, 2)})

    p_max = pothole.max_conf if pothole else 0.0
    g_dets = [d for d in (trash.detections if trash else []) if d.conf >= GARBAGE_DET_CONF]
    g_max = trash.max_conf if trash else 0.0
    g_area = sum(d.area for d in g_dets)
    coco_dets = coco.detections if coco else []
    person = _largest(coco_dets, {"person"}, GATE_CONF)
    people = [(d.box[2] - d.box[0]) * (d.box[3] - d.box[1]) for d in coco_dets if d.name == "person" and d.conf >= GATE_CONF]
    animal = _largest(coco_dets, ANIMALS, GATE_CONF)
    scores = {
        "pothole_max": round(p_max, 3), "garbage_max": round(g_max, 3), "garbage_items": len(g_dets),
        "garbage_area": round(g_area, 4), "person_box": round(person, 3), "people": len(people),
        "animal_box": round(animal, 3), "gray_std": round(std, 2),
    }

    # The photo is *of* a person, a group or an animal: never an issue, whatever the litter model
    # says (clothing and fur trigger it). Judges' check: irrelevant photos are not accepted; it also
    # keeps photos of real people out of storage.
    group = len(people) >= GATE_GROUP_N and sum(people) >= GATE_GROUP_AREA
    if person >= GATE_BOX or animal >= GATE_BOX or group:
        return Decision("not_issue", None, 0.0, "person_or_animal", scores)

    garbage_strong = g_max >= GARBAGE_ISSUE and (len(g_dets) >= GARBAGE_MIN_DETS or g_area >= GARBAGE_MIN_AREA)
    pothole_strong = p_max >= POTHOLE_ISSUE

    boxes = []
    if pothole:
        boxes += [{"cls": "pothole", "conf": round(d.conf, 3), "box": [round(v, 4) for v in d.box]}
                  for d in pothole.detections if d.conf >= POTHOLE_UNSURE]
    boxes += [{"cls": "garbage", "conf": round(d.conf, 3), "box": [round(v, 4) for v in d.box]} for d in g_dets]

    # Litter on the ground also fools the pothole model; a strong garbage signal wins unless
    # the pothole score is clearly higher.
    if garbage_strong and (not pothole_strong or g_max >= p_max):
        return Decision("issue", "garbage", g_max, "garbage_accumulation", scores, boxes)
    if pothole_strong:
        # Dark leaf litter / debris can look like a pothole; if the litter model also sees an
        # item, the two models disagree -> don't be confident, let the citizen choose.
        if g_max >= CONFLICT_GARBAGE:
            return Decision("uncertain", "pothole", p_max, "models_disagree", scores, boxes)
        return Decision("issue", "pothole", p_max, "pothole_detected", scores, boxes)

    # Weaker evidence -> ask the user. Best guess is the higher of the two.
    cand = []
    if p_max >= POTHOLE_UNSURE:
        cand.append(("pothole", p_max))
    if g_max >= GARBAGE_UNSURE:
        cand.append(("garbage", g_max))
    if cand:
        cat, conf = max(cand, key=lambda c: c[1])
        return Decision("uncertain", cat, conf, "weak_evidence", scores, boxes)
    return Decision("not_issue", None, max(p_max, g_max), "no_issue_found", scores, boxes)
