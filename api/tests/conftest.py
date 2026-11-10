"""Shared fixtures: an in-memory store, a fake signed-in caller, and a fake classifier,
so the API can be tested without Firebase credentials or the 135 MB of models."""
from __future__ import annotations

import io
import os
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import main  # noqa: E402
from app.decide import Decision  # noqa: E402
from app.security import Caller, get_caller  # noqa: E402
from app.store import MemoryStore  # noqa: E402

LAHORE = (31.5204, 74.3587)
_SEEDS = __import__('itertools').count(1000)


class FakeClassifier:
    def __init__(self):
        self.next = Decision("issue", "pothole", 0.81, "pothole_confident")

    async def __call__(self, img):
        return self.next


class CallerBox:
    def __init__(self):
        self.caller = Caller(uid="citizen-1")


@pytest.fixture
def ctx():
    store, clf, box = MemoryStore(), FakeClassifier(), CallerBox()
    main.app.state.store = store
    main.app.state.classifier = clf
    main.app.dependency_overrides[get_caller] = lambda: box.caller
    with TestClient(main.app) as client:
        yield client, store, clf, box
    main.app.dependency_overrides.clear()
    for k in ("store", "classifier"):
        if hasattr(main.app.state, k):
            delattr(main.app.state, k)


def photo(w=640, h=480, fmt="JPEG", seed=0, **save_kw) -> bytes:
    """A noisy (non-blank) synthetic road-ish photo."""
    rng = np.random.default_rng(seed)
    arr = (rng.random((h, w, 3)) * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, fmt, **save_kw)
    return buf.getvalue()


def submit(client, img=None, lat=LAHORE[0], lng=LAHORE[1], category="pothole", source="gps", **extra):
    data = {"category": category, "lat": str(lat), "lng": str(lng), "locationSource": source}
    data.update({k: v for k, v in extra.items() if v is not None})
    # a fresh photo per call unless the test passes one: the same picture twice is a duplicate now
    files = {"image": ("p.jpg", img if img is not None else photo(seed=next(_SEEDS)), "image/jpeg")}
    return client.post("/reports", data=data, files=files)
