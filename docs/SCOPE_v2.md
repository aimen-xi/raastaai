# RaastaAI — Project Scope v2 (Hackathon MVP · Pilot Concept)

> This version replaces `RaastaAI_Project_Scope.docx` (v1). It includes the judges' "approved with required changes" review and the owner's decisions:
> - no Roboflow
> - no paid AI API
> - OpenStreetMap for maps

## 1. Overview
RaastaAI is a **pilot concept** for anonymous citizen reporting of two urban problems in Pakistan: **potholes** and **garbage accumulation**.

How a report is made:
1. A citizen takes or uploads **one photo**.
2. Pretrained, self-hosted vision models suggest what the photo shows: an issue, uncertain, or not an issue.
3. The citizen **confirms or corrects** the category and confirms the location.
4. The citizen explicitly submits the report.

Rules for the AI and the dashboard:
- The AI **never creates a report on its own**.
- Admins review reports, duplicate clusters and recurring hotspots on a protected dashboard.
- RaastaAI is **not connected to any government authority**. It is presented as a pilot concept.

## 2. Objectives
1. Classify a single photo as pothole, garbage, uncertain or not an issue, with a confidence score, using public pretrained models. No training is done.
2. Let anonymous citizens submit a report, including when the AI fails or location permission is denied.
3. Strip all photo metadata (EXIF) before storage.
4. Merge duplicate reports and identify hotspots using defined, tested rules.
5. Provide an admin dashboard secured on the server (map, list, status management).

## 3. Detection approach (judge requirement 1)

No model is trained before or during the event. All models are public pretrained weights, run by us, exported to ONNX and served with `onnxruntime` by the RaastaAI API. The API runs on a free Hugging Face Space (see §6).

| Role | Model | Licence | Notes |
|---|---|---|---|
| Pothole | [FarzadNekouee YOLOv8n-seg `best.pt`](https://github.com/FarzadNekouee/YOLOv8_Pothole_Segmentation_Road_Damage_Assessment) (6.5 MB, class: Pothole) | Repo MIT · base Ultralytics AGPL-3.0 | 640 px input |
| Garbage (primary) | [turhancan97/yolov8-segment-trash-detection](https://huggingface.co/turhancan97/yolov8-segment-trash-detection) YOLOv8m-seg (54.8 MB) | Tagged MIT · base AGPL-3.0 · datasets TrashNet/TACO (MIT as listed on HF) | Class list to be confirmed in Phase 2 |
| Garbage (fallback) | [kendrickfff/YOLOv8GarbageClassification](https://huggingface.co/kendrickfff/YOLOv8GarbageClassification) YOLOv8l (87.8 MB, mAP50 0.783 reported) | Tagged MIT · base AGPL-3.0 | 1280 px input, heavier on CPU |
| Relevance gate | Official Ultralytics YOLOv8n (COCO) | AGPL-3.0 | Detects people, animals and vehicles to reject irrelevant photos |

**Licence statement:** all weights come from Ultralytics YOLOv8 (AGPL-3.0). The RaastaAI source code is therefore published publicly under **AGPL-3.0**, and the README credits every model and dataset.

**How the garbage model is chosen:** in Phase 2, both garbage candidates are tested on a staged evaluation set of about 40 images: street garbage piles, clean roads, potholes, people, animals and blank images. We keep the model with the best precision at our threshold. These detectors are trained on litter items, so "garbage accumulation" is defined as either:
- total garbage-mask area ≥ 3% of the image, or
- at least 3 detections with confidence ≥ 0.40.

Both values are calibrated in Phase 2.

## 4. Decision logic (judge requirement 3)

| Step | Rule | Outcome |
|---|---|---|
| 1 | Grayscale std-dev < 8 (blank or near-uniform image) | `not_issue` |
| 2 | Run the pothole and garbage models | — |
| 3 | Best issue score ≥ **0.50** (pothole) / garbage-accumulation rule met | `issue` + suggested category |
| 4 | Best score between **0.25** and the issue threshold | `uncertain`: the user must choose |
| 5 | No issue signal, **or** COCO gate finds a person or animal covering ≥ 15% of the image with no issue signal | `not_issue` |
| — | Model error or > 10 s | `error`: the user picks the category manually |

**Phase 2 result (2026-11-09):**
- The garbage model is **turhancan YOLOv8m-seg**; kendrickfff is dropped.
- Final rules add a person/group gate, a "models disagree → uncertain" rule and a garbage-accumulation rule (≥ 2 items or ≥ 3% mask area).
- The single source of truth for thresholds is `api/app/decide.py`. Evidence is in `docs/MODEL_EVAL.md`.
- On the evaluation set, irrelevant photos confidently accepted as issues: **0 / 12**.

Outcomes and how a report is stored:
- In every outcome, the user confirms or corrects the category before submitting.
- After `not_issue` or `error`, the user can still submit with a manual category. These reports are stored as **unverified** and shown flagged on the dashboard.
- A report is **verified** only when the AI returned `issue` and the user confirmed that category.

## 5. Functional scope

### 5.1 Citizen app (Flutter; Android build, Flutter-web fallback)

Reporting is anonymous: Firebase Anonymous Auth plus App Check. There are no accounts.

Steps:
1. **Capture:** take or upload one photo. The phone resizes it to a 1280 px maximum side and recompresses it without EXIF.
2. **Result screen:** shows one of four states: likely issue (with mask overlay and confidence), uncertain, not an issue, or analysis failed.
3. **Category confirm/correct:** Pothole or Garbage.
4. **Location:**
   - GPS is used when available, and its accuracy is shown.
   - Accuracy worse than 50 m shows a warning.
   - A **draggable map pin** (OpenStreetMap via `flutter_map`) is always available.
   - If permission is denied or no fix arrives within 10 s, the map opens at a default city centre and the user places the pin.
5. **Review and submit:** photo, category, location, and an optional note (≤ 200 characters).
6. **Receipt:** report ID, plus "merged with N nearby reports" when a duplicate is found. Receipt IDs are kept on the device only ("My reports" is optional and cut first).

**Out of scope:** live video, real-time detection, accounts, notifications.

### 5.2 Admin dashboard (React + Vite, Firebase Hosting)
- Email/password login. Access requires the `admin` custom claim, and a 403 state is shown otherwise.
- **Overview:** totals by category and by status, plus the top hotspots.
- **Map** (react-leaflet, OpenStreetMap): different marker shape and colour per category, cluster bubbles and hotspot rings.
- **Reports table:** filters for category, status, verified/unverified and location source.
- **Report detail:** photo via a short-lived signed URL; AI suggestion vs the user's category; confidence; coordinates and accuracy; cluster; status history.
- **Status change** (pending → in progress → resolved) goes **only through a server function**.

## 6. Backend (free plans only, ₨0)

**Owner constraint:** only free plans. Firebase's free **Spark** plan does **not** include Cloud Functions, and new Cloud Storage buckets also need the paid Blaze plan. The server-side code therefore runs on a free **Hugging Face Space**. Everything else stays on Firebase Spark.

| Piece | Free service | Use |
|---|---|---|
| RaastaAI API | **Hugging Face Space** (Docker, CPU basic: 2 vCPU / 16 GB, free) running a **FastAPI** app | Endpoints `/classify`, `/reports`, `/admin/status`, `/admin/image/{id}`, `/health`. Hosts the ONNX models. Writes to Firestore with the Admin SDK; the service-account key is stored as a Space **secret**. |
| Database | **Cloud Firestore** (Spark: 1 GiB, 50k reads / 20k writes per day) | `reports`, `clusters`, `rateLimits`, `reportImages` |
| Images | **Firestore `reportImages/{id}`** (bytes field) | The EXIF-stripped JPEG is re-encoded to ≤ 1280 px at q75 so it stays under ~600 KB, below Firestore's 1 MiB document limit. Only the API can read it, and only for admins. |
| Auth | **Firebase Auth** (Spark) | Anonymous sign-in for citizens; email/password plus the `admin` custom claim for admins |
| Dashboard hosting | **Firebase Hosting** (Spark) | React build |
| Rules | **Firestore Security Rules** | Deny all client writes; admin read only |

- The scope v1 rule "no FastAPI" is relaxed **only** because Cloud Functions are not free.
- The API is a stateless inference and validation service. Firebase remains the only data store and identity provider.
- A free Space sleeps after a period of inactivity. Open `/health` about 5 minutes before the demo; the client also shows "Waking up AI…" while the Space starts.
- If the Space is down, the client falls back to manual category selection (judge requirement 8). Submitting still needs the API.

### 6.1 Data model
- `reports/{id}`:
  - Category and AI result: `category`, `aiLabel` (`issue`|`uncertain`|`not_issue`|`error`), `aiCategory`, `aiConfidence`
  - User actions and verification: `userCorrected`, `userOverride`, `verification` (`verified`|`unverified`)
  - Location: `lat`, `lng`, `accuracyM`, `locationSource` (`gps`|`manual_pin`), `outsidePakistan`, `geohash`
  - Image: `imagePath`
  - Workflow: `status`, `statusHistory[]`, `clusterId`
  - Metadata: `reporterUid`, `note`, `createdAt`
- `clusters/{id}`: `category`, `centroidLat`, `centroidLng`, `geohash`, `reportCount`, `firstAt`, `lastAt`, `isHotspot`
- `rateLimits/{key}`: `windowStart`, `count`

### 6.2 Input validation (`submitReport`)

| Check | Rejected with |
|---|---|
| Body > 8 MB | **413** |
| Magic bytes not JPEG, PNG or WebP | **415** (the declared MIME type is ignored) |
| Pillow cannot decode the image, or it is > 40 MP | **400** |
| Category not in the enum | **400** |
| lat/lng missing, not finite, out of range, or exactly (0,0) | **400** |
| Required field missing | **400** `{field, error}` |
| Rate limit exceeded | **429** |

A point outside the Pakistan bounding box (lat 23–37.5, lng 60–78) is not rejected; the report is flagged `outsidePakistan`.

### 6.3 Privacy (judge requirement 5)
- The server applies `exif_transpose`, rebuilds the image from pixel data only, and re-encodes it as JPEG q85 with a 1600 px maximum side. Only that output is stored.
- An automated test asserts that the stored file has no EXIF or GPS data.
- Demos use only dataset or staged images, never real people or vehicles.

### 6.4 Duplicates and hotspots (judge requirement 6)
- **Merge:** a report joins an existing cluster when it has the same category, is within **25 m** (haversine) of the cluster centroid, and the cluster's last report is within **7 days**.
  - The nearest matching cluster wins; otherwise a new cluster is created.
  - The centroid is updated as a running mean.
  - Lookup uses the geohash-7 cell and its 8 neighbours.
- **Hotspot:** at least **3 reports within 50 m in 30 days**.

### 6.5 Security (judge requirements 7 and 8)

**Access rules:**
- Firestore: clients cannot create or update any document; reading requires the `admin` claim. All writes go through functions using the Admin SDK.
- `reportImages`: no client access at all. The dashboard fetches images through `/admin/image/{id}`, which verifies the Firebase ID token and the `admin` claim.
- Every API write endpoint verifies a Firebase ID token with the Admin SDK: anonymous for citizens, `admin` claim for status changes.
- `updateStatus` checks the `admin` claim and the status enum, and appends to `statusHistory`.

**Rate limits:**
- 5 reports per anonymous uid per 10 minutes.
- 20 reports per hashed IP per hour.

**Keys:**
- There are no paid API keys.
- Firebase config is public by design.
- Service credentials stay server-side.

## 7. Acceptance tests (judges' checks)

| Check | Test |
|---|---|
| Irrelevant photos rejected | Person, animal, blank and wall images → `not_issue` or `uncertain`; no report is created |
| Works with location permission denied | Submit with `manual_pin` → 200; missing coordinates → 400 |
| Duplicates merged | 10 m / 1 h → same cluster; 40 m → new; 8 days → new; different category → new; geohash cell boundary → merged; 3 reports in 30 days → hotspot |
| No location metadata stored | Fixture with GPS EXIF → stored object has no EXIF |
| Status protected | Non-admin call → permission-denied; direct client write → denied by rules |
| Bad input | 20 MB → 413; PDF renamed to `.jpg` → 415; truncated JPEG → 400; missing field → 400; lat = 200 → 400; 6th report → 429 |

Tests are written with pytest, the Firebase Emulator Suite and `@firebase/rules-unit-testing`.

## 8. Excluded
- Live video and real-time detection
- Citizen accounts, notifications and per-user history on the server
- Model training
- Paid AI APIs
- Google Maps
- Road cracks, manholes, streetlights and any other category
- Depth measurement
- Dispatch, government integration and any claim of an authority connection
- Predictive maintenance

## 9. Mandatory stack (revised)

| Component | Technology |
|---|---|
| Mobile app | Flutter (Dart) |
| Vision models | Public pretrained YOLOv8 weights → ONNX → `onnxruntime` |
| Backend | Firebase Spark (Auth, Firestore, Hosting, Rules) + FastAPI on a free Hugging Face Space (inference and all writes) |
| Admin dashboard | React (JavaScript, Vite) |
| Maps | OpenStreetMap: `flutter_map` / `react-leaflet` |

## 10. Success criteria
- Every row in §7 passes.
- A full demo runs end to end with staged images in under 90 seconds.
- The project is presented honestly as a pilot concept.
