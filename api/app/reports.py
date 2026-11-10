"""Report creation and admin status changes: the only code that writes report data."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

from .clustering import hotspot_count, merged_centroid, pick_cluster
from .config import settings
from .errors import ApiError
from .geo import geohash, haversine_m, neighbourhood, outside_pakistan
from .images import dhash_bands, hamming
from .ratelimit import check_and_count
from .store import Store

CATEGORIES = {"pothole", "garbage"}
LOCATION_SOURCES = {"gps", "manual_pin"}
STATUSES = ("pending", "in_progress", "resolved")
# The AI is sure this is not a road photo at all: no override (keeps people's photos out too).
HARD_REJECT = {"blank_image", "person_or_animal"}
_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def new_id(prefix: str) -> str:
    return prefix + "".join(secrets.choice(_ID_ALPHABET) for _ in range(6))


@dataclass
class NewReport:
    category: str
    lat: float
    lng: float
    accuracy_m: float | None
    location_source: str
    note: str
    uid: str
    ip_key: str
    image_jpeg: bytes
    image_w: int
    image_h: int
    ai: dict | None  # AI result {o, c, p, r, src: client|server} or None (AI really unavailable)
    image_sha256: str = ""
    image_dhash: str = ""
    demo_sample: bool = False  # one of the app's bundled staged photos: exempt from the reuse check


def verification_fields(ai: dict | None, category: str) -> dict:
    """What the AI said vs. what the citizen chose. Three tiers, used for admin priority:
    verified     AI said issue AND the citizen agreed
    unverified   AI unsure, citizen changed the category, or AI unavailable
    ai_rejected  AI found no issue, citizen reported anyway (needs a note; never makes hotspots)"""
    if ai is None:
        return {"aiOutcome": "error", "aiCategory": None, "aiConfidence": None, "aiReason": None,
                "aiCheckedBy": None, "userCorrected": False, "userOverride": True, "verification": "unverified"}
    outcome, ai_cat = ai.get("o"), ai.get("c")
    if outcome == "not_issue":
        ver = "ai_rejected"
    elif outcome == "issue" and ai_cat == category:
        ver = "verified"
    else:
        ver = "unverified"
    return {
        "aiOutcome": outcome,
        "aiCategory": ai_cat,
        "aiConfidence": ai.get("p"),
        "aiReason": ai.get("r"),
        "aiCheckedBy": ai.get("src", "client"),
        "userCorrected": ai_cat is not None and ai_cat != category,
        "userOverride": outcome == "not_issue",
        "verification": ver,
    }


def create_report(store: Store, r: NewReport, now: datetime) -> dict:
    if r.category not in CATEGORIES:
        raise ApiError(400, "invalid_category", "category must be 'pothole' or 'garbage'.", "category")
    if r.location_source not in LOCATION_SOURCES:
        raise ApiError(400, "invalid_location_source", "locationSource must be 'gps' or 'manual_pin'.", "locationSource")

    ver = verification_fields(r.ai, r.category)
    rejected = ver["verification"] == "ai_rejected"
    if rejected and ver["aiReason"] in HARD_REJECT:
        raise ApiError(422, "not_a_road_photo",
                       "This photo doesn't show a road problem (it looks blank, or shows a person or animal). "
                       "Please take a photo of the pothole or garbage.", "image")
    if rejected and len(r.note) < settings.override_note_min_chars:
        raise ApiError(400, "note_required",
                       f"Our AI found no pothole or garbage in this photo. To report it anyway, describe the "
                       f"problem in at least {settings.override_note_min_chars} characters.", "note")

    gh = geohash(r.lat, r.lng, settings.geohash_precision)
    cells = neighbourhood(r.lat, r.lng, settings.geohash_precision)
    report_id = new_id("RA-")

    def tx_fn(tx):
        # ---- reads (all before any write) ----
        rl = [
            check_and_count(tx, f"submit_uid_{r.uid}", *settings.submit_per_uid, now),
            check_and_count(tx, f"submit_ip_{r.ip_key}", *settings.submit_per_ip, now),
        ]
        if rejected:
            rl.append(check_and_count(tx, f"override_uid_{r.uid}", *settings.override_per_uid, now))
        reused_from = check_photo_reuse(tx, r)
        clusters = tx.query("clusters", [("category", "==", r.category), ("geohash", "in", cells)])
        nearby = tx.query("reports", [("category", "==", r.category), ("geohash", "in", cells)])

        cid, cdoc, dist = pick_cluster(clusters, r.category, r.lat, r.lng, now)
        # AI-rejected reports never count toward a hotspot (theirs or anyone else's)
        hot_n = hotspot_count(nearby, r.category, r.lat, r.lng, now) - (1 if rejected else 0)
        is_hot = not rejected and hot_n >= settings.hotspot_min_reports

        # ---- writes ----
        for key, doc in rl:
            tx.set("rateLimits", key, doc)
        if cid is None:
            cid = new_id("C-")
            count = 1
            tx.set("clusters", cid, {
                "category": r.category, "centroidLat": r.lat, "centroidLng": r.lng, "geohash": gh,
                "reportCount": 1, "firstAt": now, "lastAt": now, "isHotspot": is_hot, "nearbyCount30d": hot_n,
                "status": "pending",
            })
            merged = False
        else:
            count = cdoc["reportCount"] + 1
            clat, clng = merged_centroid(cdoc, r.lat, r.lng)
            tx.update("clusters", cid, {
                "centroidLat": clat, "centroidLng": clng, "geohash": geohash(clat, clng, settings.geohash_precision),
                "reportCount": count, "lastAt": now,
                "isHotspot": bool(cdoc.get("isHotspot")) or is_hot,
                "nearbyCount30d": max(hot_n, cdoc.get("nearbyCount30d", 0)),
            })
            merged = True

        doc = {
            "category": r.category, "lat": r.lat, "lng": r.lng, "accuracyM": r.accuracy_m,
            "locationSource": r.location_source, "outsidePakistan": outside_pakistan(r.lat, r.lng),
            "geohash": gh, "status": "pending", "statusHistory": [], "clusterId": cid,
            "reporterUid": r.uid, "note": r.note, "createdAt": now,
            "imageWidth": r.image_w, "imageHeight": r.image_h, "imageBytes": len(r.image_jpeg),
            "imageSha256": r.image_sha256, "imageDHash": r.image_dhash,
            "imageDHashBands": dhash_bands(r.image_dhash) if r.image_dhash and not r.demo_sample else [],
            "photoReusedFrom": reused_from, "demoSample": r.demo_sample,
            **ver,
        }
        tx.set("reports", report_id, doc)
        tx.set("reportImages", report_id, {"jpeg": r.image_jpeg, "createdAt": now})
        return {
            "reportId": report_id, "clusterId": cid, "clusterReportCount": count, "merged": merged,
            "mergedDistanceM": round(dist, 1) if dist is not None else None,
            "hotspot": is_hot, "status": "pending", "verification": doc["verification"],
            "photoReusedFrom": reused_from,
        }

    return store.run(tx_fn)


def check_photo_reuse(tx, r: NewReport) -> str | None:
    """Same picture seen before?  (exact file, or visually the same after resize/recompress)
    - by the same person (anywhere)   -> 409 duplicate_report (double tap / resubmission)
    - by someone else within 25 m     -> allowed, grouped as usual, marked photoReusedFrom
    - by someone else further away    -> 409 photo_reused (one photo can't report two places)"""
    if r.demo_sample or not r.image_dhash:
        return None
    matches = []
    for rid, d in tx.query("reports", [("imageDHashBands", "array_contains_any", dhash_bands(r.image_dhash))]):
        same = d.get("imageSha256") == r.image_sha256 or (
            d.get("imageDHash") and hamming(d["imageDHash"], r.image_dhash) <= settings.photo_match_max_bits)
        if same:
            matches.append((haversine_m(r.lat, r.lng, d["lat"], d["lng"]), rid, d))
    if not matches:
        return None
    matches.sort(key=lambda m: m[0])
    mine = [m for m in matches if m[2].get("reporterUid") == r.uid]
    if mine:
        raise ApiError(409, "duplicate_report",
                       f"You already reported this photo ({mine[0][1]}). There's no need to send it again.", "image")
    dist, rid, _ = matches[0]
    if dist <= settings.merge_radius_m:
        return rid
    raise ApiError(409, "photo_reused",
                   "This photo was already used for a report at another location. "
                   "Please take a new photo of the problem where you are.", "image")


def change_status(store: Store, report_id: str, new_status: str, admin_uid: str, now: datetime) -> dict:
    if new_status not in STATUSES:
        raise ApiError(400, "invalid_status", f"status must be one of {', '.join(STATUSES)}.", "status")

    def tx_fn(tx):
        doc = tx.get("reports", report_id)
        if doc is None:
            raise ApiError(404, "not_found", "Report not found.")
        old = doc.get("status")
        history = list(doc.get("statusHistory") or [])
        if old != new_status:
            history.append({"from": old, "to": new_status, "by": admin_uid, "at": now})
            tx.update("reports", report_id, {"status": new_status, "statusHistory": history})
        return {"reportId": report_id, "status": new_status, "previous": old, "changed": old != new_status}

    return store.run(tx_fn)


def classify_rate_limit(store: Store, uid: str, now: datetime) -> None:
    def tx_fn(tx):
        key, doc = check_and_count(tx, f"classify_uid_{uid}", *settings.classify_per_uid, now)
        tx.set("rateLimits", key, doc)

    store.run(tx_fn)
