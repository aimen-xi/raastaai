"""Coordinates: validation, haversine distance and geohash cells for proximity queries."""
from __future__ import annotations

import math

from .config import settings
from .errors import ApiError

_B32 = "0123456789bcdefghjkmnpqrstuvwxyz"
EARTH_R = 6_371_008.8  # metres


def parse_coords(lat_raw, lng_raw) -> tuple[float, float]:
    out = []
    for name, raw in (("lat", lat_raw), ("lng", lng_raw)):
        if raw is None or str(raw).strip() == "":
            raise ApiError(400, "missing_field", f"{name} is required.", name)
        try:
            v = float(raw)
        except (TypeError, ValueError):
            raise ApiError(400, "invalid_coordinates", f"{name} must be a number.", name)
        if not math.isfinite(v):
            raise ApiError(400, "invalid_coordinates", f"{name} must be a finite number.", name)
        out.append(v)
    lat, lng = out
    if not -90 <= lat <= 90:
        raise ApiError(400, "invalid_coordinates", "lat must be between -90 and 90.", "lat")
    if not -180 <= lng <= 180:
        raise ApiError(400, "invalid_coordinates", "lng must be between -180 and 180.", "lng")
    if lat == 0 and lng == 0:
        raise ApiError(400, "invalid_coordinates", "0,0 is not a real location (GPS not ready?).", "lat")
    return lat, lng


def outside_pakistan(lat: float, lng: float) -> bool:
    return not (settings.pk_lat[0] <= lat <= settings.pk_lat[1] and settings.pk_lng[0] <= lng <= settings.pk_lng[1])


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def geohash(lat: float, lng: float, precision: int) -> str:
    lat_r, lng_r = [-90.0, 90.0], [-180.0, 180.0]
    out, bits, ch, even = [], 0, 0, True
    while len(out) < precision:
        rng, v = (lng_r, lng) if even else (lat_r, lat)
        mid = (rng[0] + rng[1]) / 2
        if v >= mid:
            ch = (ch << 1) | 1
            rng[0] = mid
        else:
            ch <<= 1
            rng[1] = mid
        even = not even
        bits += 1
        if bits == 5:
            out.append(_B32[ch])
            bits, ch = 0, 0
    return "".join(out)


def cell_size(precision: int) -> tuple[float, float]:
    """(lat_degrees, lng_degrees) of one geohash cell."""
    lng_bits = math.ceil(precision * 5 / 2)
    lat_bits = math.floor(precision * 5 / 2)
    return 180.0 / (2 ** lat_bits), 360.0 / (2 ** lng_bits)


def neighbourhood(lat: float, lng: float, precision: int) -> list[str]:
    """The cell containing the point plus its 8 neighbours (deduplicated, max 9 -> fits Firestore 'in')."""
    dlat, dlng = cell_size(precision)
    cells = []
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            la = max(-89.999999, min(89.999999, lat + i * dlat))
            ln = ((lng + j * dlng + 180) % 360) - 180
            g = geohash(la, ln, precision)
            if g not in cells:
                cells.append(g)
    return cells
