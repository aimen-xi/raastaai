"""All tunable limits and rules in one place. Values can be overridden by environment variables
(e.g. on the Hugging Face Space), but the defaults are the documented ones (docs/SCOPE_v2.md)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default, cast=str):
    v = os.environ.get(name)
    return default if v is None or v == "" else cast(v)


@dataclass(frozen=True)
class Settings:
    # --- input validation (judge check: bad input handled) ---
    max_upload_bytes: int = _env("MAX_UPLOAD_BYTES", 8 * 1024 * 1024, int)
    max_pixels: int = _env("MAX_PIXELS", 40_000_000, int)
    note_max_chars: int = 200
    stored_max_side: int = 1280
    stored_max_bytes: int = 900_000  # Firestore document limit is 1 MiB
    # --- duplicates & hotspots (judge requirement 6) ---
    merge_radius_m: float = 25.0
    merge_window_days: float = 7.0
    hotspot_radius_m: float = 50.0
    hotspot_window_days: float = 30.0
    hotspot_min_reports: int = 3
    geohash_precision: int = 7  # ~153 m x 153 m cells; cell + 8 neighbours covers > 50 m
    # --- Pakistan soft bounds (flag only, never reject) ---
    pk_lat: tuple = (23.0, 37.5)
    pk_lng: tuple = (60.0, 78.0)
    # --- rate limits (judge requirement 7) ---
    submit_per_uid: tuple = (5, 600)       # 5 reports / 10 min per anonymous user
    submit_per_ip: tuple = (20, 3600)      # 20 reports / hour per IP
    classify_per_uid: tuple = (30, 600)    # 30 analyses / 10 min per user
    override_per_uid: tuple = (2, 3600)    # 2 'AI found nothing, report anyway' / hour per user
    override_note_min_chars: int = 15      # ...and each needs a short description of the problem
    # --- reused photos ---
    photo_match_max_bits: int = 6          # dHash Hamming distance that still counts as 'the same picture'
    sample_dir: str = _env("SAMPLE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "app", "assets", "samples"))
    # --- classification tickets ---
    ticket_secret: str = _env("TICKET_SECRET", "dev-only-secret-change-me")
    ticket_ttl_s: int = 3600
    ip_salt: str = _env("IP_HASH_SALT", "dev-only-salt")
    # --- runtime ---
    model_dir: str = _env("MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "models"))
    model_threads: int = _env("MODEL_THREADS", 2, int)
    firebase_key_path: str = _env("FIREBASE_KEY_PATH", "")
    firebase_key_json: str = _env("FIREBASE_SERVICE_ACCOUNT_JSON", "")  # HF Space secret
    allowed_origins: list = field(default_factory=lambda: [o for o in _env("ALLOWED_ORIGINS", "*").split(",") if o])


settings = Settings()
