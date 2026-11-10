"""End-to-end API tests, one section per judge check (see docs/SCOPE_v2.md test matrix)."""
from __future__ import annotations

import io
import os

import numpy as np
from datetime import datetime, timedelta, timezone

import piexif
from PIL import Image

from app import main
from app.decide import Decision
from app.security import Caller, make_ticket
from conftest import LAHORE, photo, submit

M_PER_DEG_LAT = 111_195.0


def north(lat, metres):
    return lat + metres / M_PER_DEG_LAT


# ---------------------------------------------------------------- judge: bad input handled
def test_huge_file_rejected_413(ctx):
    client, *_ = ctx
    big = b"\xff\xd8\xff" + b"0" * (9 * 1024 * 1024)
    r = client.post("/classify", files={"image": ("big.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and r.json()["error"] == "file_too_large"


def test_non_image_rejected_415_even_if_named_jpg(ctx):
    client, *_ = ctx
    r = client.post("/classify", files={"image": ("evil.jpg", b"%PDF-1.7 not a photo", "image/jpeg")})
    assert r.status_code == 415 and r.json()["field"] == "image"


def test_truncated_jpeg_rejected_400(ctx):
    client, *_ = ctx
    r = client.post("/classify", files={"image": ("t.jpg", photo()[:3000], "image/jpeg")})
    assert r.status_code == 400 and r.json()["error"] == "corrupt_image"


def test_decompression_bomb_rejected(ctx):
    client, *_ = ctx
    buf = io.BytesIO()
    Image.new("L", (8000, 6000)).save(buf, "PNG")  # 48 MP, tiny file
    r = client.post("/classify", files={"image": ("b.png", buf.getvalue(), "image/png")})
    assert r.status_code == 400 and r.json()["error"] == "image_too_big"


def test_missing_image_400(ctx):
    client, *_ = ctx
    r = client.post("/reports", data={"category": "pothole", "lat": "31.5", "lng": "74.3", "locationSource": "gps"})
    assert r.status_code == 400 and r.json()["field"] == "image"


def test_missing_fields_400(ctx):
    client, *_ = ctx
    for drop, field in (("category", "category"), ("lat", "lat"), ("locationSource", "locationSource")):
        data = {"category": "pothole", "lat": "31.5", "lng": "74.3", "locationSource": "gps"}
        del data[drop]
        r = client.post("/reports", data=data, files={"image": ("p.jpg", photo(), "image/jpeg")})
        assert r.status_code == 400, drop
        assert r.json()["field"] == field


def test_bad_coordinates_400(ctx):
    client, *_ = ctx
    for lat, lng in (("200", "74"), ("31", "-190"), ("nan", "74"), ("inf", "74"), ("abc", "74"), ("0", "0")):
        r = submit(client, lat=lat, lng=lng)
        assert r.status_code == 400 and r.json()["error"] == "invalid_coordinates", (lat, lng)


def test_bad_category_and_note(ctx):
    client, *_ = ctx
    assert submit(client, category="graffiti").json()["error"] == "invalid_category"
    assert submit(client, note="x" * 201).json()["field"] == "note"
    assert submit(client, accuracyM="-5").json()["field"] == "accuracyM"


# ---------------------------------------------------------------- judge: no location metadata stored
def test_stored_image_has_no_exif_or_gps(ctx):
    client, store, *_ = ctx
    gps = {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: ((31, 1), (31, 1), (1234, 100)),
           piexif.GPSIFD.GPSLongitudeRef: b"E", piexif.GPSIFD.GPSLongitude: ((74, 1), (21, 1), (3100, 100))}
    exif = piexif.dump({"0th": {piexif.ImageIFD.Make: b"PhoneCo", piexif.ImageIFD.Orientation: 6},
                        "Exif": {}, "GPS": gps, "1st": {}, "thumbnail": None})
    src = photo(exif=exif)
    assert piexif.load(src)["GPS"], "fixture must really contain GPS"

    r = submit(client, img=src)
    assert r.status_code == 201, r.text
    rid = r.json()["reportId"]
    stored = bytes(store.data["reportImages"][rid]["jpeg"])
    assert b"Exif" not in stored[:4096] and b"GPS" not in stored
    with Image.open(io.BytesIO(stored)) as im:
        assert not im.getexif()
        assert "exif" not in im.info and "icc_profile" not in im.info
        assert im.size == (480, 640)  # orientation 6 applied before stripping (upright)
    assert len(stored) < 900_000


def test_admin_image_endpoint_also_clean(ctx):
    client, store, _, box = ctx
    rid = submit(client).json()["reportId"]
    box.caller = Caller("admin-1", admin=True, anonymous=False)
    r = client.get(f"/admin/reports/{rid}/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "no-store" in r.headers["cache-control"]
    assert not Image.open(io.BytesIO(r.content)).getexif()


# ---------------------------------------------------------------- judge: works when location denied
def test_location_denied_manual_pin_works(ctx):
    client, store, *_ = ctx
    r = submit(client, source="manual_pin")  # no accuracyM: user dropped the pin by hand
    assert r.status_code == 201, r.text
    doc = store.data["reports"][r.json()["reportId"]]
    assert doc["locationSource"] == "manual_pin" and doc["accuracyM"] is None


def test_outside_pakistan_flagged_not_rejected(ctx):
    client, store, *_ = ctx
    r = submit(client, lat=51.5, lng=-0.12)
    assert r.status_code == 201
    assert store.data["reports"][r.json()["reportId"]]["outsidePakistan"] is True


# ---------------------------------------------------------------- judge: AI never auto-creates; tickets
def test_classify_returns_suggestion_and_creates_nothing(ctx):
    client, store, *_ = ctx
    r = client.post("/classify", files={"image": ("p.jpg", photo(), "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "issue" and body["category"] == "pothole" and body["ticket"]
    assert not store.data.get("reports")


def test_verified_only_with_valid_ticket_and_agreement(ctx):
    client, store, *_ = ctx
    img = photo(seed=1)
    ticket = client.post("/classify", files={"image": ("p.jpg", img, "image/jpeg")}).json()["ticket"]
    ok = submit(client, img=img, aiTicket=ticket).json()
    assert ok["verification"] == "verified"

    img2 = photo(seed=11)
    ticket2 = client.post("/classify", files={"image": ("p.jpg", img2, "image/jpeg")}).json()["ticket"]
    corrected = submit(client, img=img2, aiTicket=ticket2, category="garbage", lat=33.7, lng=73.0).json()
    assert corrected["verification"] == "unverified"
    assert store.data["reports"][corrected["reportId"]]["userCorrected"] is True


def test_tampered_or_foreign_ticket_is_ignored(ctx):
    client, store, *_ = ctx
    img = photo(seed=2)
    ticket = client.post("/classify", files={"image": ("p.jpg", img, "image/jpeg")}).json()["ticket"]
    payload, sig = ticket.split(".")
    forged = payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB") + "." + sig
    main.app.state.classifier = None  # no server re-check: show the bad tickets alone earn nothing
    assert submit(client, img=img, aiTicket=forged).json()["verification"] == "unverified"
    # a genuine ticket for a DIFFERENT photo doesn't transfer
    assert submit(client, img=photo(seed=3), aiTicket=ticket, lat=30.0, lng=70.0).json()["verification"] == "unverified"
    # a self-made ticket with the wrong secret
    import app.security as sec
    real = sec.settings
    object.__setattr__(real, "ticket_secret", "attacker")
    try:
        evil = make_ticket("x", "issue", "pothole", 0.99, "citizen-1")
    finally:
        object.__setattr__(real, "ticket_secret", "dev-only-secret-change-me")
    assert submit(client, img=photo(seed=12), aiTicket=evil, lat=29.0, lng=71.0).json()["verification"] == "unverified"


def test_manual_fallback_when_ai_unavailable(ctx):
    client, *_ = ctx
    main.app.state.classifier = None
    r = client.post("/classify", files={"image": ("p.jpg", photo(), "image/jpeg")})
    assert r.status_code == 503
    r = submit(client)  # citizen picks category by hand
    assert r.status_code == 201 and r.json()["verification"] == "unverified"


def _ticket(client, img):
    return client.post("/classify", files={"image": ("p.jpg", img, "image/jpeg")}).json()["ticket"]


def test_blank_or_person_photo_cannot_be_reported(ctx):
    client, store, clf, _ = ctx
    for reason in ("blank_image", "person_or_animal"):
        clf.next = Decision("not_issue", None, 0.0, reason)
        img = photo(seed=40)
        r = submit(client, img=img, aiTicket=_ticket(client, img), note="there really is a big pothole here")
        assert r.status_code == 422 and r.json()["error"] == "not_a_road_photo"
    assert store.data.get("reports", {}) == {}


def test_no_issue_override_needs_a_note_and_is_ai_rejected(ctx):
    client, store, clf, _ = ctx
    clf.next = Decision("not_issue", None, 0.1, "no_issue_found")
    img = photo(seed=4)
    t = _ticket(client, img)
    r = submit(client, img=img, aiTicket=t)
    assert r.status_code == 400 and r.json()["error"] == "note_required"
    r = submit(client, img=img, aiTicket=t, note="  short  ")
    assert r.status_code == 400 and r.json()["error"] == "note_required"
    r = submit(client, img=img, aiTicket=t, note="Deep pothole hidden under water")
    assert r.status_code == 201 and r.json()["verification"] == "ai_rejected"
    doc = store.data["reports"][r.json()["reportId"]]
    assert doc["userOverride"] is True and doc["aiReason"] == "no_issue_found" and doc["aiCheckedBy"] == "client"


def test_no_issue_overrides_limited_to_two_per_hour(ctx):
    client, _, clf, _ = ctx
    clf.next = Decision("not_issue", None, 0.1, "no_issue_found")
    codes = []
    for i in range(3):
        img = photo(seed=50 + i)
        codes.append(submit(client, img=img, aiTicket=_ticket(client, img), lat=31.50 + i * 0.01,
                            note="Garbage dumped behind the wall").status_code)
    assert codes == [201, 201, 429]
    clf.next = Decision("issue", "pothole", 0.9, "pothole_detected")  # normal reports unaffected
    img = photo(seed=60)
    assert submit(client, img=img, aiTicket=_ticket(client, img), lat=31.6).status_code == 201


def test_ai_rejected_reports_never_make_a_hotspot(ctx):
    client, store, clf, _ = ctx
    clf.next = Decision("not_issue", None, 0.1, "no_issue_found")
    for i in range(2):
        box_uid = f"spam-{i}"  # different users so the per-user override limit isn't what stops it
        ctx[3].caller = type(ctx[3].caller)(uid=box_uid)
        img = photo(seed=70 + i)
        r = submit(client, img=img, aiTicket=_ticket(client, img), lat=LAHORE[0] + i * 0.0001,
                   note="Pothole near the bus stop here")
        assert r.status_code == 201 and r.json()["hotspot"] is False
    # one genuine report next to two AI-rejected ones: still only 1 counting report -> no hotspot
    ctx[3].caller = type(ctx[3].caller)(uid="real-user")
    clf.next = Decision("issue", "pothole", 0.9, "pothole_detected")
    img = photo(seed=80)
    r = submit(client, img=img, aiTicket=_ticket(client, img), lat=LAHORE[0] + 0.0002)
    assert r.status_code == 201 and r.json()["hotspot"] is False


def test_server_rechecks_when_phone_could_not_reach_ai(ctx):
    client, store, clf, _ = ctx
    # no ticket (phone timed out) but the photo IS a pothole -> verified by the server
    clf.next = Decision("issue", "pothole", 0.88, "pothole_detected")
    r = submit(client, img=photo(seed=90))
    assert r.status_code == 201 and r.json()["verification"] == "verified"
    assert store.data["reports"][r.json()["reportId"]]["aiCheckedBy"] == "server"
    # no ticket and a random photo -> the server finds nothing -> note required / ai_rejected
    clf.next = Decision("not_issue", None, 0.05, "no_issue_found")
    assert submit(client, img=photo(seed=91), lat=31.55).json()["error"] == "note_required"
    r = submit(client, img=photo(seed=91), lat=31.55, note="Overflowing garbage bins here")
    assert r.json()["verification"] == "ai_rejected"


# ---------------------------------------------------------------- judge: duplicates merged / hotspots
def test_same_spot_merges(ctx):
    client, *_ = ctx
    a = submit(client).json()
    b = submit(client, lat=north(LAHORE[0], 10)).json()
    assert b["merged"] and b["clusterId"] == a["clusterId"] and b["clusterReportCount"] == 2
    assert 9 <= b["mergedDistanceM"] <= 11


def test_far_or_other_category_does_not_merge(ctx):
    client, *_ = ctx
    a = submit(client).json()
    far = submit(client, lat=north(LAHORE[0], 40)).json()
    other = submit(client, category="garbage").json()
    assert not far["merged"] and far["clusterId"] != a["clusterId"]
    assert not other["merged"] and other["clusterId"] != a["clusterId"]


def test_merge_window_expires_after_7_days(ctx, monkeypatch):
    client, *_ = ctx
    t0 = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    monkeypatch.setattr(main, "now_utc", lambda: t0)
    a = submit(client).json()
    monkeypatch.setattr(main, "now_utc", lambda: t0 + timedelta(days=8))
    b = submit(client).json()
    assert not b["merged"] and b["clusterId"] != a["clusterId"]


def test_merge_across_geohash_cell_boundary(ctx):
    from app.geo import cell_size, geohash
    client, *_ = ctx
    dlat, _ = cell_size(7)
    # find a cell edge near Lahore and put two reports 6 m either side of it
    base = (int(LAHORE[0] / dlat) + 1) * dlat
    a_lat, b_lat = base - 3 / M_PER_DEG_LAT, base + 3 / M_PER_DEG_LAT
    assert geohash(a_lat, LAHORE[1], 7) != geohash(b_lat, LAHORE[1], 7)
    a = submit(client, lat=a_lat).json()
    b = submit(client, lat=b_lat).json()
    assert b["merged"] and b["clusterId"] == a["clusterId"]


def test_hotspot_after_three_reports_within_50m(ctx, monkeypatch):
    client, _, _, box = ctx
    t0 = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    results = []
    for i, (metres, day) in enumerate(((0, 0), (35, 3), (45, 10))):  # 3 different clusters, same area
        monkeypatch.setattr(main, "now_utc", lambda d=day: t0 + timedelta(days=d))
        box.caller = Caller(f"u{i}")
        results.append(submit(client, lat=north(LAHORE[0], metres)).json())
    assert [r["hotspot"] for r in results] == [False, False, True]


def test_no_hotspot_when_older_than_30_days(ctx, monkeypatch):
    client, _, _, box = ctx
    t0 = datetime(2026, 9, 1, 9, tzinfo=timezone.utc)
    for i, day in enumerate((0, 1, 40)):
        monkeypatch.setattr(main, "now_utc", lambda d=day: t0 + timedelta(days=d))
        box.caller = Caller(f"u{i}")
        last = submit(client, lat=north(LAHORE[0], 30 * i)).json()
    assert last["hotspot"] is False


# ---------------------------------------------------------------- judge: status protected
def test_status_change_requires_admin(ctx):
    client, store, _, box = ctx
    rid = submit(client).json()["reportId"]
    r = client.post(f"/admin/reports/{rid}/status", json={"status": "resolved"})
    assert r.status_code == 403
    assert client.get(f"/admin/reports/{rid}/image").status_code == 403
    assert store.data["reports"][rid]["status"] == "pending"

    box.caller = Caller("admin-1", admin=True, anonymous=False)
    r = client.post(f"/admin/reports/{rid}/status", json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["previous"] == "pending"
    hist = store.data["reports"][rid]["statusHistory"]
    assert hist[-1]["by"] == "admin-1" and hist[-1]["to"] == "in_progress"
    assert client.post(f"/admin/reports/{rid}/status", json={"status": "done!"}).status_code == 400
    assert client.post("/admin/reports/RA-NOPE00/status", json={"status": "resolved"}).status_code == 404


def test_no_token_is_401():
    from fastapi.testclient import TestClient
    from app.store import MemoryStore
    main.app.state.store, main.app.state.classifier = MemoryStore(), None
    try:
        with TestClient(main.app) as c:
            r = c.post("/admin/reports/RA-X/status", json={"status": "resolved"})
            assert r.status_code == 401
            r = c.post("/admin/reports/RA-X/status", json={"status": "resolved"},
                       headers={"Authorization": "Bearer not-a-real-token"})
            assert r.status_code == 401
    finally:
        del main.app.state.store, main.app.state.classifier


def test_public_status_reveals_no_location(ctx):
    client, *_ = ctx
    rid = submit(client).json()["reportId"]
    body = client.get(f"/reports/{rid}").json()
    assert body["status"] == "pending"
    assert not {"lat", "lng", "reporterUid", "note", "geohash"} & set(body)
    assert client.get("/reports/RA-NOPE00").status_code == 404


# ---------------------------------------------------------------- judge: anonymous reporting rate-limited
def test_sixth_report_in_10_min_is_429(ctx):
    client, *_ = ctx
    for i in range(5):
        assert submit(client, lat=30 + i, lng=70).status_code == 201
    r = submit(client, lat=36, lng=70)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_rate_limit_window_resets(ctx, monkeypatch):
    client, *_ = ctx
    t0 = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    monkeypatch.setattr(main, "now_utc", lambda: t0)
    for i in range(5):
        submit(client, lat=30 + i, lng=70)
    monkeypatch.setattr(main, "now_utc", lambda: t0 + timedelta(minutes=11))
    assert submit(client, lat=36, lng=70).status_code == 201


def test_ip_limit_applies_across_new_anonymous_users(ctx):
    client, _, _, box = ctx
    for i in range(20):
        box.caller = Caller(f"fresh-{i}")
        assert submit(client, lat=25 + i * 0.5, lng=70, headers=None).status_code == 201
    box.caller = Caller("fresh-final")
    assert submit(client, lat=36.9, lng=70).status_code == 429


def test_spoofed_forwarded_for_does_not_bypass_ip_limit(ctx):
    client, _, _, box = ctx
    for i in range(20):
        box.caller = Caller(f"spoof-{i}")
        r = client.post("/reports", data={"category": "pothole", "lat": str(25 + i * 0.5), "lng": "70",
                                          "locationSource": "gps"},
                        files={"image": ("p.jpg", photo(seed=200 + i), "image/jpeg")},
                        headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"})
        assert r.status_code == 201
    box.caller = Caller("spoof-final")
    r = client.post("/reports", data={"category": "pothole", "lat": "36.9", "lng": "70", "locationSource": "gps"},
                    files={"image": ("p.jpg", photo(seed=299), "image/jpeg")},
                    headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.9"})
    assert r.status_code == 429


def test_classify_rate_limit(ctx):
    client, *_ = ctx
    img = photo(64, 64)
    for _ in range(30):
        assert client.post("/classify", files={"image": ("p.jpg", img, "image/jpeg")}).status_code == 200
    assert client.post("/classify", files={"image": ("p.jpg", img, "image/jpeg")}).status_code == 429


def test_health(ctx):
    client, *_ = ctx
    assert client.get("/health").json()["ok"] is True


# ---------------------------------------------------------------- reused photos
def _jpeg(raw: bytes, size=None, quality=90) -> bytes:
    im = Image.open(io.BytesIO(raw))
    if size:
        im = im.resize(size)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _scene(seed=0) -> bytes:
    """A smooth 'real photo'-like image (random noise isn't stable under resizing, real photos are)."""
    rng = np.random.default_rng(seed)
    small = (rng.random((6, 8, 3)) * 255).astype("uint8")
    return _jpeg(_png(Image.fromarray(small).resize((800, 600), Image.BICUBIC)))


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_dhash_survives_resize_and_recompression():
    from app.images import dhash, hamming

    a = _scene(1)
    b = _jpeg(a, size=(400, 300), quality=60)  # e.g. forwarded on WhatsApp
    ha, hb = (dhash(Image.open(io.BytesIO(x)).convert("RGB")) for x in (a, b))
    hc = dhash(Image.open(io.BytesIO(_scene(2))).convert("RGB"))
    assert hamming(ha, hb) <= 6 < hamming(ha, hc)


def test_same_person_same_photo_twice_is_a_duplicate(ctx):
    client, store, *_ = ctx
    img = _scene(3)
    first = submit(client, img=img)
    assert first.status_code == 201
    again = submit(client, img=img)  # double tap
    assert again.status_code == 409 and again.json()["error"] == "duplicate_report"
    elsewhere = submit(client, img=img, lat=LAHORE[0] + 0.05)
    assert elsewhere.status_code == 409 and elsewhere.json()["error"] == "duplicate_report"
    assert len(store.data["reports"]) == 1


def test_same_photo_other_person_same_spot_is_grouped_and_marked(ctx):
    client, store, _, box = ctx
    img = _scene(4)
    first = submit(client, img=img).json()
    box.caller = Caller(uid="neighbour")
    r = submit(client, img=_jpeg(img, size=(640, 480), quality=70), lat=LAHORE[0] + 0.0001)  # ~11 m, recompressed
    assert r.status_code == 201
    body = r.json()
    assert body["merged"] is True and body["clusterId"] == first["clusterId"]
    assert body["photoReusedFrom"] == first["reportId"]


def test_same_photo_other_person_other_place_is_rejected(ctx):
    client, store, _, box = ctx
    img = _scene(5)
    assert submit(client, img=img).status_code == 201
    box.caller = Caller(uid="faker")
    r = submit(client, img=_jpeg(img, size=(400, 300), quality=55), lat=LAHORE[0] + 0.01)  # ~1.1 km away
    assert r.status_code == 409 and r.json()["error"] == "photo_reused"
    assert len(store.data["reports"]) == 1


def test_bundled_demo_samples_may_be_reused(ctx):
    client, store, _, box = ctx
    sample = os.path.join(os.path.dirname(__file__), "..", "..", "app", "assets", "samples", "pothole.jpg")
    data = open(sample, "rb").read()
    a = submit(client, img=data)
    box.caller = Caller(uid="judge-2")
    b = submit(client, img=data, lat=LAHORE[0] + 0.02)
    c = submit(client, img=data, lat=LAHORE[0] + 0.04)
    assert [x.status_code for x in (a, b, c)] == [201, 201, 201]
    assert store.data["reports"][a.json()["reportId"]]["demoSample"] is True
