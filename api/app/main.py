"""RaastaAI API (FastAPI). Runs on a free Hugging Face Space; data lives in Firebase (Spark).

Endpoints
  GET  /health                         liveness + whether models are loaded (also used to wake the Space)
  POST /classify                       photo -> AI suggestion + signed ticket (never creates a report)
  POST /reports                        create a report (citizen confirmed the category)
  GET  /reports/{id}                   public receipt status (no location, no photo)
  POST /admin/reports/{id}/status      admin only
  GET  /admin/reports/{id}/image       admin only (photo bytes, EXIF-free)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .config import settings
from .errors import ApiError
from .geo import parse_coords
from .images import clean_for_storage, validate_image
from .reports import NewReport, change_status, classify_rate_limit, create_report
from .security import Caller, client_ip, get_caller, ip_key, make_ticket, read_ticket, require_admin
from .store import MemoryStore

log = logging.getLogger("raasta")
CLASSIFY_TIMEOUT_S = 20
_LOCAL_KEY = os.path.join(os.path.dirname(__file__), "..", "..", "secrets", "firebase-admin.json")


# ---------------------------------------------------------------------------------------------
class Classifier:
    """Loads the 3 ONNX models once; runs them off the event loop, one photo at a time."""

    def __init__(self, model_dir: str, threads: int):
        from .vision import load_models

        self.models = load_models(model_dir, ["pothole", "trash_turhancan", "coco"], threads)
        self._sem = asyncio.Semaphore(1)

    def _run(self, img):
        from .decide import decide

        m = self.models
        return decide(img, m["pothole"](img), m["trash_turhancan"](img), m["coco"](img))

    async def __call__(self, img):
        async with self._sem:
            return await asyncio.wait_for(run_in_threadpool(self._run, img), CLASSIFY_TIMEOUT_S)


def _init_store():
    if os.environ.get("STORE", "firestore") == "memory":
        log.warning("STORE=memory: data is NOT persisted (local demo only)")
        return MemoryStore()
    import firebase_admin
    from firebase_admin import credentials, firestore

    from .store import FirestoreStore

    if not firebase_admin._apps:
        if settings.firebase_key_json:
            cred = credentials.Certificate(json.loads(settings.firebase_key_json))
        elif settings.firebase_key_path:
            cred = credentials.Certificate(settings.firebase_key_path)
        elif os.path.exists(_LOCAL_KEY):  # local development only (secrets/ is gitignored)
            cred = credentials.Certificate(_LOCAL_KEY)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    return FirestoreStore(firestore.client())


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("SPACE_ID") and settings.ticket_secret.startswith("dev-only"):
        raise RuntimeError("Set the TICKET_SECRET and IP_HASH_SALT secrets on the Space before deploying.")
    if not hasattr(app.state, "store"):
        app.state.store = _init_store()
    if not hasattr(app.state, "classifier"):
        try:
            app.state.classifier = Classifier(settings.model_dir, settings.model_threads)
        except Exception:  # missing model files etc. -> API still works, client falls back to manual
            log.exception("models failed to load; /classify will return 503")
            app.state.classifier = None
    yield


app = FastAPI(title="RaastaAI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type"], allow_credentials=False)


@app.middleware("http")
async def body_size_guard(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > settings.max_upload_bytes + 64 * 1024:
        return JSONResponse(ApiError(413, "file_too_large", "Photo is larger than 8 MB.", "image").body(), 413)
    return await call_next(request)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, e: ApiError):
    return JSONResponse(e.body(), status_code=e.status, headers=e.headers)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, e: RequestValidationError):
    err = e.errors()[0] if e.errors() else {}
    field = str(err.get("loc", ["", "body"])[-1])
    code = "missing_field" if err.get("type") == "missing" else "invalid_field"
    return JSONResponse({"error": code, "message": f"{field}: {err.get('msg', 'invalid')}", "field": field}, 400)


def get_store(request: Request):
    return request.app.state.store


def get_classifier(request: Request):
    return request.app.state.classifier


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def read_upload(image: UploadFile | None) -> bytes:
    if image is None:
        raise ApiError(400, "missing_field", "image is required.", "image")
    data = await image.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise ApiError(413, "file_too_large", "Photo is larger than 8 MB.", "image")
    return data


# ---------------------------------------------------------------------------------------------
@app.get("/health")
async def health(request: Request):
    return {"ok": True, "models": request.app.state.classifier is not None,
            "store": type(request.app.state.store).__name__}


def _sample_hashes() -> set[str]:
    import hashlib

    try:
        return {hashlib.sha256(open(os.path.join(settings.sample_dir, f), "rb").read()).hexdigest()
                for f in os.listdir(settings.sample_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))}
    except OSError:
        return set()


SAMPLE_SHA256 = _sample_hashes()  # the app's bundled demo photos may be reused anywhere

_APK = os.path.join(os.path.dirname(__file__), "..", "..", "release", "RaastaAI.apk")


@app.get("/download/RaastaAI.apk")
async def download_apk():
    """Android test build for the demo (Firebase Hosting's free plan doesn't allow .apk files)."""
    if not os.path.isfile(_APK):
        raise ApiError(404, "not_found", "No Android build available.")
    return FileResponse(_APK, media_type="application/vnd.android.package-archive", filename="RaastaAI.apk")


@app.post("/classify")
async def classify(image: UploadFile | None = File(None), caller: Caller = Depends(get_caller),
                   store=Depends(get_store), classifier=Depends(get_classifier)):
    data = await read_upload(image)
    v = validate_image(data)
    await run_in_threadpool(classify_rate_limit, store, caller.uid, now_utc())
    if classifier is None:
        raise ApiError(503, "classifier_unavailable", "AI is unavailable. Please choose the category yourself.")
    try:
        d = await classifier(v.image)
    except asyncio.TimeoutError:
        raise ApiError(503, "classifier_timeout", "AI took too long. Please choose the category yourself.")
    out = d.to_dict()
    out["ticket"] = make_ticket(v.sha256, d.outcome, d.category, d.confidence, caller.uid, d.reason)
    return out


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@app.post("/reports", status_code=201)
async def submit_report(
    request: Request,
    image: UploadFile | None = File(None),
    category: str | None = Form(None),
    lat: str | None = Form(None),
    lng: str | None = Form(None),
    accuracyM: str | None = Form(None),
    locationSource: str | None = Form(None),
    note: str | None = Form(None),
    aiTicket: str | None = Form(None),
    caller: Caller = Depends(get_caller),
    store=Depends(get_store),
    classifier=Depends(get_classifier),
):
    if not category:
        raise ApiError(400, "missing_field", "category is required.", "category")
    if not locationSource:
        raise ApiError(400, "missing_field", "locationSource is required.", "locationSource")
    la, ln = parse_coords(lat, lng)
    acc = None
    if accuracyM not in (None, ""):
        try:
            acc = float(accuracyM)
        except ValueError:
            raise ApiError(400, "invalid_field", "accuracyM must be a number.", "accuracyM")
        if not (0 <= acc <= 100_000):
            raise ApiError(400, "invalid_field", "accuracyM is out of range.", "accuracyM")
    clean_note = _CTRL.sub("", (note or "")).strip()
    if len(clean_note) > settings.note_max_chars:
        raise ApiError(400, "invalid_field", f"note must be at most {settings.note_max_chars} characters.", "note")

    data = await read_upload(image)
    v = validate_image(data)
    jpeg = await run_in_threadpool(clean_for_storage, v.image)
    ai = read_ticket(aiTicket, v.sha256, caller.uid)
    if ai is not None:
        ai["src"] = "client"
    elif classifier is not None:
        # The phone couldn't reach the AI (or sent no/expired ticket): check the photo here, so a
        # random photo can't skip the AI just by going "manual" (anti-spam).
        try:
            d = await classifier(v.image)
            ai = {"o": d.outcome, "c": d.category, "p": round(d.confidence, 4), "r": d.reason, "src": "server"}
        except Exception:
            ai = None  # AI really unavailable -> stays a manual, unverified report
    nr = NewReport(category=category.strip().lower(), lat=la, lng=ln, accuracy_m=acc,
                   location_source=locationSource.strip(), note=clean_note, uid=caller.uid,
                   ip_key=ip_key(client_ip(request)), image_jpeg=jpeg, image_w=v.width, image_h=v.height, ai=ai,
                   image_sha256=v.sha256, image_dhash=v.dhash, demo_sample=v.sha256 in SAMPLE_SHA256)
    return await run_in_threadpool(create_report, store, nr, now_utc())


@app.get("/reports/{report_id}")
async def report_status(report_id: str, store=Depends(get_store)):
    doc = await run_in_threadpool(store.get, "reports", report_id)
    if doc is None:
        raise ApiError(404, "not_found", "Report not found.")
    cluster = await run_in_threadpool(store.get, "clusters", doc["clusterId"]) or {}
    return {"reportId": report_id, "category": doc["category"], "status": doc["status"],
            "verification": doc.get("verification"), "clusterReportCount": cluster.get("reportCount", 1),
            "createdAt": doc["createdAt"].isoformat()}


class StatusBody(BaseModel):
    status: str


@app.post("/admin/reports/{report_id}/status")
async def admin_status(report_id: str, body: StatusBody, caller: Caller = Depends(get_caller), store=Depends(get_store)):
    require_admin(caller)
    return await run_in_threadpool(change_status, store, report_id, body.status, caller.uid, now_utc())


@app.get("/admin/reports/{report_id}/image")
async def admin_image(report_id: str, caller: Caller = Depends(get_caller), store=Depends(get_store)):
    require_admin(caller)
    doc = await run_in_threadpool(store.get, "reportImages", report_id)
    if doc is None:
        raise ApiError(404, "not_found", "Image not found.")
    return Response(bytes(doc["jpeg"]), media_type="image/jpeg",
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
