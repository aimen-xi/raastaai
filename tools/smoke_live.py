"""Live smoke test: the real API code + real models + the real Firebase project.

Signs in a throwaway anonymous citizen and a throwaway admin (custom token with admin=true),
runs the judge flows against Firestore, then deletes everything it created.

Usage: python tools/smoke_live.py
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FIREBASE_KEY_PATH", os.path.join(ROOT, "secrets", "firebase-admin.json"))
sys.path.insert(0, os.path.join(ROOT, "api"))

from fastapi.testclient import TestClient  # noqa: E402
from firebase_admin import auth, firestore  # noqa: E402
from PIL import Image  # noqa: E402

from app import main  # noqa: E402

CFG = json.load(open(os.path.join(ROOT, "config", "firebase-web.json"), encoding="utf-8"))
IDT = "https://identitytoolkit.googleapis.com/v1/accounts:"


def idt(method, body):
    req = urllib.request.Request(f"{IDT}{method}?key={CFG['apiKey']}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    return bool(cond)


def main_():
    results, made = [], {"reports": set(), "reportImages": set(), "clusters": set(), "rateLimits": set(), "users": set()}
    with TestClient(main.app) as c:
        db = firestore.client()
        try:
            citizen = idt("signUp", {"returnSecureToken": True})
            made["users"].add(citizen["localId"])
            made["rateLimits"].update({f"submit_uid_{citizen['localId']}", f"classify_uid_{citizen['localId']}"})
            H = {"Authorization": f"Bearer {citizen['idToken']}"}

            admin_uid = "smoke-admin-" + str(random.randint(1000, 9999))
            ct = auth.create_custom_token(admin_uid, {"admin": True}).decode()
            admin = idt("signInWithCustomToken", {"token": ct, "returnSecureToken": True})
            made["users"].add(admin_uid)
            A = {"Authorization": f"Bearer {admin['idToken']}"}

            h = c.get("/health").json()
            results.append(check("health: models loaded, Firestore store", h["models"] and h["store"] == "FirestoreStore", h))

            results.append(check("no token -> 401", c.post("/classify", files={"image": ("x.jpg", b"x")}).status_code == 401))

            img = open(os.path.join(ROOT, "eval", "set1", "garbage", "garbage_01.jpg"), "rb").read() \
                if os.path.exists(os.path.join(ROOT, "eval", "set1", "garbage", "garbage_01.jpg")) else None
            if img is None:
                import csv
                rows = list(csv.DictReader(open(os.path.join(ROOT, "eval", "set1", "manifest.csv"))))
                img = open(os.path.join(ROOT, "eval", "set1", next(r["file"] for r in rows if r["label"] == "garbage")), "rb").read()
            r = c.post("/classify", files={"image": ("g.jpg", img, "image/jpeg")}, headers=H)
            cl = r.json()
            results.append(check("classify garbage photo", r.status_code == 200, f"{cl.get('outcome')} {cl.get('category')} {cl.get('confidence')}"))

            blank = io.BytesIO(); Image.new("RGB", (640, 480), (120, 120, 120)).save(blank, "JPEG")
            b = c.post("/classify", files={"image": ("b.jpg", blank.getvalue(), "image/jpeg")}, headers=H).json()
            results.append(check("blank photo -> not_issue", b["outcome"] == "not_issue", b["reason"]))

            lat, lng = 24.86 + random.random() / 100, 67.0 + random.random() / 100
            cat = cl.get("category") or "garbage"
            form = {"category": cat, "lat": str(lat), "lng": str(lng), "accuracyM": "12", "locationSource": "gps",
                    "aiTicket": cl.get("ticket", "")}
            r1 = c.post("/reports", data=form, files={"image": ("g.jpg", img, "image/jpeg")}, headers=H)
            j1 = r1.json()
            results.append(check("submit report", r1.status_code == 201, j1))
            if r1.status_code == 201:
                made["reports"].add(j1["reportId"]); made["reportImages"].add(j1["reportId"]); made["clusters"].add(j1["clusterId"])

            form2 = dict(form, lat=str(lat + 10 / 111_195), locationSource="manual_pin", accuracyM="", aiTicket="")
            img2 = open(os.path.join(ROOT, "eval", "set1", "garbage", "garbage_02.jpg"), "rb").read()  # a different photo
            r2 = c.post("/reports", data=form2, files={"image": ("g.jpg", img2, "image/jpeg")}, headers=H)
            j2 = r2.json()
            results.append(check("second report 10 m away merges (manual pin, no AI)",
                                 r2.status_code == 201 and j2.get("merged") and j2.get("clusterId") == j1.get("clusterId"), j2))
            if r2.status_code == 201:
                made["reports"].add(j2["reportId"]); made["reportImages"].add(j2["reportId"])

            r3 = c.post("/reports", data=dict(form, aiTicket=""), files={"image": ("g.jpg", img, "image/jpeg")}, headers=H)
            results.append(check("same photo again from same user -> 409 duplicate", r3.status_code == 409
                                 and r3.json().get("error") == "duplicate_report", r3.json()))

            stored = bytes(db.collection("reportImages").document(j1["reportId"]).get().to_dict()["jpeg"])
            with Image.open(io.BytesIO(stored)) as im:
                results.append(check("stored image in Firestore has no EXIF", not im.getexif() and "exif" not in im.info,
                                     f"{len(stored)} bytes"))

            rid = j1["reportId"]
            results.append(check("citizen status change -> 403",
                                 c.post(f"/admin/reports/{rid}/status", json={"status": "resolved"}, headers=H).status_code == 403))
            r = c.post(f"/admin/reports/{rid}/status", json={"status": "in_progress"}, headers=A)
            results.append(check("admin status change -> 200", r.status_code == 200, r.json()))
            results.append(check("public status shows in_progress, no location",
                                 (lambda s: s["status"] == "in_progress" and "lat" not in s)(c.get(f"/reports/{rid}").json())))
            r = c.get(f"/admin/reports/{rid}/image", headers=A)
            results.append(check("admin image endpoint", r.status_code == 200 and r.headers["content-type"] == "image/jpeg"))
        finally:
            for coll in ("reports", "reportImages", "clusters", "rateLimits"):
                for d in made[coll]:
                    db.collection(coll).document(d).delete()
            # IP-keyed rate-limit docs from this run
            for d in db.collection("rateLimits").list_documents():
                if d.id.startswith("submit_ip_"):
                    d.delete()
            for u in made["users"]:
                try:
                    auth.delete_user(u)
                except Exception:
                    pass
            print("cleanup done")
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main_())
