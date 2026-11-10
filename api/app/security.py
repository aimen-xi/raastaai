"""Identity, admin check, classification tickets and IP hashing.

- Every write endpoint needs a Firebase ID token (anonymous for citizens).
- Admin endpoints need the `admin` custom claim, checked HERE on the server (judge requirement 7).
- A classification "ticket" is an HMAC-signed record of what the AI said about *this exact photo*
  (bound by SHA-256). submitReport trusts AI fields only from a valid ticket, so a client cannot
  mark its own report as "AI-verified".
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Request

from .config import settings
from .errors import ApiError


@dataclass
class Caller:
    uid: str
    admin: bool = False
    anonymous: bool = True


def verify_firebase_token(token: str) -> Caller:
    from firebase_admin import auth  # imported lazily so unit tests don't need credentials

    try:
        claims = auth.verify_id_token(token)
    except Exception as e:  # expired, malformed, wrong project...
        raise ApiError(401, "unauthenticated", "Sign-in token is missing or invalid.") from e
    provider = (claims.get("firebase") or {}).get("sign_in_provider")
    return Caller(uid=claims["uid"], admin=claims.get("admin") is True, anonymous=provider == "anonymous")


def bearer(request: Request) -> str:
    h = request.headers.get("authorization", "")
    if not h.lower().startswith("bearer "):
        raise ApiError(401, "unauthenticated", "Sign-in token is missing or invalid.")
    return h[7:].strip()


def get_caller(request: Request) -> Caller:
    """FastAPI dependency; tests override it."""
    return verify_firebase_token(bearer(request))


def require_admin(caller: Caller) -> Caller:
    if not caller.admin:
        raise ApiError(403, "forbidden", "Admin access required.")
    return caller


LOOPBACK = {"127.0.0.1", "::1"}


def client_ip(request: Request) -> str:
    # Behind the Cloudflare tunnel every request arrives from loopback; Cloudflare's edge
    # overwrites CF-Connecting-IP with the real client address, so trust it only in that case.
    peer = request.client.host if request.client else ""
    if peer in LOOPBACK and request.headers.get("cf-connecting-ip"):
        return request.headers["cf-connecting-ip"].strip()
    # The client can put anything in X-Forwarded-For; the HF proxy APPENDS the address it saw,
    # so the last entry is the one we can trust.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def ip_key(ip: str) -> str:
    return hashlib.sha256((settings.ip_salt + ip).encode()).hexdigest()[:20]


# --- classification tickets -------------------------------------------------------------
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_ticket(image_sha256: str, outcome: str, category: str | None, confidence: float, uid: str,
                reason: str | None = None) -> str:
    payload = json.dumps({"h": image_sha256, "o": outcome, "c": category, "p": round(confidence, 4), "r": reason,
                          "u": uid, "t": int(time.time())}, separators=(",", ":")).encode()
    sig = hmac.new(settings.ticket_secret.encode(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def read_ticket(ticket: str | None, image_sha256: str, uid: str) -> dict | None:
    """Return the AI result if the ticket is authentic, fresh, for this photo and this user; else None."""
    if not ticket:
        return None
    try:
        p64, s64 = ticket.split(".", 1)
        payload = _unb64(p64)
        good = hmac.new(settings.ticket_secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(good, _unb64(s64)):
            return None
        data = json.loads(payload)
    except Exception:
        return None
    if data.get("h") != image_sha256 or data.get("u") != uid:
        return None
    if time.time() - data.get("t", 0) > settings.ticket_ttl_s:
        return None
    return data
