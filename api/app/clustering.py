"""Duplicate merging and hotspot rules (judge requirement 6). Pure functions, unit-tested.

MERGE:   a new report joins an existing cluster when it has the SAME category, is within
         25 m (haversine) of the cluster centroid, and the cluster's last report is less than
         7 days old. The nearest such cluster wins; otherwise a new cluster is created.
HOTSPOT: a cluster is a hotspot when >= 3 reports of the same category (including the new one)
         lie within 50 m of the new report in the last 30 days. Reports the AI rejected
         ("no issue found", sent anyway) never count.
Candidates come from the point's geohash-7 cell + its 8 neighbours (>= ~130 m each way at
Pakistan's latitudes), so nothing within 50 m can be missed at a cell boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .config import settings
from .geo import haversine_m


def _as_dt(v) -> datetime:
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))


def pick_cluster(clusters: list[tuple[str, dict]], category: str, lat: float, lng: float, now: datetime):
    """Return (cluster_id, cluster_doc, distance_m) of the cluster to merge into, or (None, None, None)."""
    best = (None, None, None)
    window = timedelta(days=settings.merge_window_days)
    for cid, c in clusters:
        if c.get("category") != category:
            continue
        if now - _as_dt(c["lastAt"]) > window:
            continue
        d = haversine_m(lat, lng, c["centroidLat"], c["centroidLng"])
        if d <= settings.merge_radius_m and (best[2] is None or d < best[2]):
            best = (cid, c, d)
    return best


def merged_centroid(c: dict, lat: float, lng: float) -> tuple[float, float]:
    n = c["reportCount"]
    return (c["centroidLat"] * n + lat) / (n + 1), (c["centroidLng"] * n + lng) / (n + 1)


def hotspot_count(reports: list[tuple[str, dict]], category: str, lat: float, lng: float, now: datetime) -> int:
    """Number of same-category reports within 50 m in the last 30 days, INCLUDING the new one."""
    window = timedelta(days=settings.hotspot_window_days)
    n = 1
    for _, r in reports:
        if r.get("category") != category or r.get("verification") == "ai_rejected":
            continue
        if now - _as_dt(r["createdAt"]) > window:
            continue
        if haversine_m(lat, lng, r["lat"], r["lng"]) <= settings.hotspot_radius_m:
            n += 1
    return n
