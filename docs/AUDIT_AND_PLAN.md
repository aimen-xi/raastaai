# RaastaAI — Scope Audit & Build Plan (MVP)

Inputs: `RaastaAI_Project_Scope.docx`, judges' "approved with required changes" review, model repo
[FarzadNekouee/YOLOv8_Pothole_Segmentation_Road_Damage_Assessment](https://github.com/FarzadNekouee/YOLOv8_Pothole_Segmentation_Road_Damage_Assessment).
Constraint from owner: **no Roboflow**, treat as MVP.
Reviewers: Architect, Backend, Frontend, UI/UX.

---

## 1. Model facts

| Item | Finding |
|---|---|
| Model | YOLOv8n-seg, fine-tuned, **single class: Pothole**, 640×640 input |
| Weights | `model/best.pt` (6.48 MB) is committed to the repo, so no training is needed |
| Licence | Repo is MIT; Ultralytics YOLOv8 is **AGPL-3.0**, so our repo must be public under AGPL-3.0 |
| Dataset | 780 images (Kaggle/Roboflow "pothole segmentation"). The README gives no metrics. |
| Gap | **No garbage class.** Garbage needs a second approach (see Decision D1). |

## 2. Gap table: judges' requirements vs scope doc

| # | Judge requirement / check | Scope doc today | Verdict | Fix |
|---|---|---|---|---|
| 1 | Pretrained model or vision API; licence stated | Roboflow hosted API | **Conflicts** | Self-hosted `best.pt` exported to ONNX, plus (D1) a vision LLM for garbage and to reject irrelevant photos. Licence stated in the README. |
| 2 | Photo only, no live video | Live preview + periodic frames | **Conflicts** | Single photo, taken or uploaded |
| 3 | AI never auto-creates; uncertain / not-an-issue; threshold; user corrects | "Confirm" only | Partial | Three outcomes plus a "failed" state, fixed thresholds (§4), category picker, explicit Submit |
| 4 | Location denied / poor accuracy, adjust pin, validate | Auto GPS only | **Missing** | Draggable pin always shown; manual-pin path; accuracy warning above 50 m; coordinate validation |
| 5 | Strip EXIF; staged demo images | — | **Missing** | Re-encode on the server (Pillow, pixel data only); automated test; demo with dataset images only |
| 6 | Duplicate-merge and hotspot rules, tested | "Group nearby" (vague) | **Missing** | Rules in §4, with unit tests |
| 7 | Admin protected on the server; rate-limit anonymous reports | Security Rules mention only | Partial | Admin custom claim; status changes only through a function; clients cannot write anything; rate limits |
| 8 | Keys server-side; manual category if AI fails | Keys server-side | Partial | `aiLabel:error` → manual category → report marked `unverified` |
| ✔ | Irrelevant photos rejected | — | **Missing** | Blank-image pre-check, YOLO threshold, LLM scene gate |
| ✔ | Bad input handled | Generic | **Missing** | 413/415/400/429 contract (§4) |

**Cut from scope:** live camera / real-time detection, citizen registration and login, "view my reports" on the server (replaced by local receipt IDs), notifications, the `users` collection, and any "authorities" or "municipal" framing (present it as a **pilot concept**). The doc's section 8 exclusions stay.

## 3. Target architecture

```
Flutter app (anonymous auth + App Check)
   │  photo (≤1280px, re-compressed)                 React admin (Firebase Hosting)
   ▼                                                  │  email login + admin claim
Cloud Functions 2nd gen (Python)                      ▼
   classify      → blank check → YOLO-ONNX → [LLM gate]  → decision (never writes)
   submitReport  → validate → strip EXIF → Storage → Firestore → cluster txn → rate limit
   updateStatus  → admin claim only
   getImageUrl   → admin claim → 15-min signed URL
Firestore: reports, clusters, rateLimits      Storage: private (read/write = false)
```
- Python functions are Firebase-native, so the "Firebase only / no FastAPI" rule still holds.
- `onnxruntime` replaces ultralytics/torch at runtime: about 50 MB instead of about 800 MB, and fast cold starts.
- Function settings: 2 GiB memory, `min_instances=1` on demo day.
- **The Blaze plan is required**; set a budget alert.
- Maps: **OpenStreetMap** (flutter_map / react-leaflet), which needs no key or billing, instead of Google Maps (D2).

## 4. Rules

**Classification thresholds** (to be calibrated on about 30 staged images)
- Blank pre-check: grayscale std-dev < 8 → `not_issue`
- Pothole: YOLO max confidence ≥ 0.50 → `issue` · 0.25–0.50 → `uncertain` · < 0.25 → no pothole
- Garbage (D1 = LLM): `garbage_conf` ≥ 0.70 → `issue` · 0.40–0.70 → `uncertain`
- LLM scene `irrelevant` (people, animals, indoor) → `not_issue`, which overrides YOLO
- Timeout (>10 s) or error → `error` → manual category
- A report is **verified** only when the AI said `issue` **and** the user confirmed it. Every other path is stored as `unverified`, with `userCorrected` / `userOverride` flags.

**Duplicates and hotspots**
- Merge: same category, ≤ **25 m** (haversine) from the cluster centroid, and cluster `lastAt` within **7 days**. Join the closest match; otherwise create a new cluster. The centroid is a running mean.
- Hotspot: ≥ **3 reports within 50 m in 30 days**.
- Lookup: geohash-7 cell plus its 8 neighbours, then filter in code.

**Input validation** (`submitReport`)
- Body ≤ 8 MB → else 413
- Magic bytes JPEG/PNG/WebP → else 415
- Pillow verify; > 40 MP rejected
- Category must be in the enum
- lat/lng: finite, within range, not (0,0); outside Pakistan's bounding box → warning flag
- Missing field → 400 `{field, error}`

**Rate limits:** 5 reports per anonymous uid per 10 min, 20 per hashed IP per hour, otherwise 429.

**Security**
- Firestore: clients have no create/update; read requires the `admin` claim.
- Storage: deny everything; the dashboard uses signed URLs.

## 5. Judge-check test matrix

| Check | Automated test |
|---|---|
| Irrelevant photos rejected | Person / cat / blank / wall fixtures → `not_issue` or `uncertain`, and no report is created |
| Location denied | `manual_pin` with no accuracy → 200; missing lat/lng → 400 |
| Duplicates grouped | 10 m / 1 h → same cluster · 40 m → new · 8 days → new · different category → new · cell boundary → merges · 3 in 30 days → hotspot |
| No location metadata | Upload a fixture with GPS EXIF → stored object has an empty GPS block (piexif) |
| Admin-only status | Non-admin → permission-denied; direct client write → denied by rules; Storage read → denied |
| Bad input | 20 MB → 413 · PDF renamed .jpg → 415 · truncated JPEG → 400 · no category → 400 · lat=200 / NaN → 400 · 6th report → 429 |

## 6. Phased plan (each phase needs owner approval before it starts)

| Phase | Deliverable | Owner role |
|---|---|---|
| **0. Decisions & Scope v2** | Answers to D1–D3; revised scope doc that states the model, licence, cuts and rules | Architect |
| **1. UI/UX mocks** | Clickable HTML mocks: citizen flow (all states) + admin dashboard; palette and copy | UI/UX |
| **2. Model prep** | Download `best.pt`, export to ONNX, parity check against ultralytics, calibrate thresholds on a staged set | Architect/BE |
| **3. Backend** | Firebase project, the four functions, rules, clustering, pytest + emulator suite (§5) | BE |
| **4. Citizen app** | Flutter photo → classify → confirm/correct → location (GPS/pin) → submit → receipt | FE |
| **5. Admin dashboard** | React: login, KPIs, map with clusters/hotspots, table, detail, status change | FE |
| **6. Integration & demo** | Run every judge check end to end, demo script, fallback screenshots, README with licence and "pilot concept" | All |

**Cut first if short on time:** mask overlay → "my reports" → date filters → charts → (run Flutter as web).
**Never cut:** result states, manual category, location fallback, server-side admin.

## 7. Decisions (owner, 2026-11-09)

- **D1 — Garbage detection:** the Claude API has no free tier, so we use **public pretrained garbage YOLO weights**. Primary: turhancan97 YOLOv8m-seg. Fallback: kendrickfff YOLOv8l. A Phase 2 bake-off picks one. The official YOLOv8n COCO model acts as the relevance gate. Details in `SCOPE_v2.md` §3–4.
- **D2 — Maps:** **OpenStreetMap**.
- **D3 — Environment (still open):** Firebase project on the Blaze plan; Flutter SDK and Python 3.11 installed locally.
