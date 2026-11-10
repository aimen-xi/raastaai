"""Seed staged demo reports into Firestore through the REAL API code path (validation, EXIF strip,
merge + hotspot rules), using only the bundled dataset sample photos. Every seeded ID is recorded
in tools/.seeded.json so `--reset` removes exactly what was added.

Usage:
  python tools/seed_demo.py            # add ~14 reports around Lahore (2 hotspots, merged duplicates)
  python tools/seed_demo.py --reset    # delete everything this script added
"""
from __future__ import annotations

import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "api"))
STATE = os.path.join(ROOT, "tools", ".seeded.json")
SAMPLES = os.path.join(ROOT, "app", "assets", "samples")
M = 1 / 111_195  # degrees latitude per metre

# (name, lat, lng, category, sample, offsets in metres for repeat reports)
SPOTS = [
    ("Kalma Chowk", 31.5040, 74.3311, "pothole", "pothole", [0, 8, 15, 35]),     # merged + hotspot
    ("Liberty Market lane", 31.5106, 74.3446, "garbage", "garbage", [0, 10, 40]),  # hotspot (2 clusters)
    ("Model Town Link Rd", 31.4833, 74.3260, "pothole", "pothole", [0, 12]),      # merged pair
    ("Johar Town G block", 31.4697, 74.2728, "garbage", "garbage", [0]),
    ("Ferozepur Rd", 31.4920, 74.3430, "pothole", "pothole", [0]),
    ("Gulberg III", 31.5155, 74.3500, "garbage", "road", [0]),                    # AI said not_issue; manual
    ("Shadman", 31.5390, 74.3270, "pothole", "road", [0]),                         # manual pin, unverified
]


def seed():
    from fastapi.testclient import TestClient

    from app import main
    from app.security import Caller, get_caller

    ids = json.load(open(STATE)) if os.path.exists(STATE) else []
    with TestClient(main.app) as c:
        n = 0
        for name, lat, lng, cat, sample, offsets in SPOTS:
            img = open(os.path.join(SAMPLES, f"{sample}.jpg"), "rb").read()
            for off in offsets:
                n += 1
                uid = f"demo-citizen-{n}"  # distinct seeded "devices" so rate limits don't trip
                main.app.dependency_overrides[get_caller] = lambda u=uid: Caller(u)
                ticket = c.post("/classify", files={"image": ("s.jpg", img, "image/jpeg")}).json().get("ticket")
                manual = sample == "road" or n % 4 == 0
                r = c.post("/reports", files={"image": ("s.jpg", img, "image/jpeg")}, data={
                    "category": cat, "lat": str(lat + off * M), "lng": str(lng + random.uniform(-3, 3) * M),
                    "locationSource": "manual_pin" if manual else "gps",
                    **({} if manual else {"accuracyM": str(random.choice([6, 9, 12, 18, 40]))}),
                    "note": f"Staged demo report near {name}", "aiTicket": ticket or "",
                }, headers={"X-Forwarded-For": f"198.51.100.{n}"})
                body = r.json()
                print(r.status_code, name, body.get("reportId"), "merged" if body.get("merged") else "",
                      "HOTSPOT" if body.get("hotspot") else "", body.get("verification"))
                if r.status_code == 201:
                    ids.append(body["reportId"])
        main.app.dependency_overrides.clear()
    json.dump(ids, open(STATE, "w"))
    print(f"\n{len(ids)} seeded report IDs saved to {STATE}")


def reset():
    if not os.path.exists(STATE):
        print("nothing to reset")
        return
    ids = json.load(open(STATE))
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "delete_report.py"), *ids], check=True)
    import firebase_admin
    from firebase_admin import firestore
    db = firestore.client() if firebase_admin._apps else None
    if db is None:
        from firebase_admin import credentials
        firebase_admin.initialize_app(credentials.Certificate(os.path.join(ROOT, "secrets", "firebase-admin.json")))
        db = firestore.client()
    for d in db.collection("rateLimits").list_documents():
        if "demo-citizen-" in d.id or d.id.startswith("submit_ip_"):
            d.delete()
    os.remove(STATE)
    print("reset done")


if __name__ == "__main__":
    reset() if "--reset" in sys.argv else seed()
