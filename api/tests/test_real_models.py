"""Judge check 'irrelevant photos (people, animals, blank images) are not accepted as issues',
run against the REAL ONNX models. Skipped when the models aren't on disk (e.g. CI: models aren't committed)."""
from __future__ import annotations

import csv
import os

import pytest
from PIL import Image

from app.config import settings
from app.vision import open_upright

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
EVAL = os.path.join(ROOT, "eval", "set1")
NEEDED = ["pothole.onnx", "trash_turhancan.onnx", "coco.onnx"]
pytestmark = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(settings.model_dir, f)) for f in NEEDED), reason="models not present")


@pytest.fixture(scope="module")
def clf():
    from app.main import Classifier
    return Classifier(settings.model_dir, settings.model_threads)


def run(clf, img):
    m = clf.models
    from app.decide import decide
    return decide(img, m["pothole"](img), m["trash_turhancan"](img), m["coco"](img))


@pytest.mark.parametrize("colour", [(0, 0, 0), (255, 255, 255), (128, 128, 128), (40, 90, 160)])
def test_blank_images_not_issue(clf, colour):
    d = run(clf, Image.new("RGB", (800, 600), colour))
    assert d.outcome == "not_issue" and d.reason == "blank_image"


def _files(label):
    """Eval photos for a label; empty when eval/set1 isn't downloaded (CI: photos aren't committed)."""
    manifest = os.path.join(EVAL, "manifest.csv")
    if not os.path.exists(manifest):
        return []
    with open(manifest, newline="") as f:
        return [r["file"] for r in csv.DictReader(f) if r["label"] == label]


@pytest.mark.parametrize("rel", _files("neg_person"))
def test_people_photos_not_issue(clf, rel):
    d = run(clf, open_upright(os.path.join(EVAL, rel)))
    assert d.outcome != "issue", d


@pytest.mark.parametrize("rel", _files("neg_road"))
def test_clean_roads_not_confident_issue(clf, rel):
    d = run(clf, open_upright(os.path.join(EVAL, rel)))
    assert d.outcome != "issue" or d.confidence < 0.6, d
