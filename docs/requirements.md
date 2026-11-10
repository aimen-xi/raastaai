# Requirements

## Problem statement

Potholes and illegal garbage dumps go unreported, or get reported vaguely: no photo, no exact location, many duplicates. That makes it hard for city staff to know what to fix first.

RaastaAI lets a citizen report one with a single photo and a map pin. An AI model *suggests* the category, and the citizen always confirms it. Admins get grouped, ranked reports and hotspots.

This is a **pilot concept**: it isn't connected to any government authority.

## Users

| User | Needs |
|---|---|
| Citizen (anonymous) | Report a road problem in under a minute, without creating an account; check its status later |
| Admin (pilot staff) | See real problems first, without duplicates; view photo and location; change status; see recurring hotspots |
| Judge / evaluator | Try the product on their own device; check the AI and rule edge cases |

## Functional requirements

| ID | Requirement | Priority (Must / Should / Stretch) | Status |
|----|-------------|------------------------------------|--------|
| FR-01 | Citizen can take or pick **one photo** (no video) | Must | Done |
| FR-02 | AI suggests pothole / garbage / uncertain / not an issue, with confidence and outlined areas; it **never creates a report by itself** | Must | Done |
| FR-03 | Citizen confirms or changes the category before anything is saved | Must | Done |
| FR-04 | If the AI is unavailable, the citizen can still report with a manual category (marked unverified) | Must | Done |
| FR-05 | Location: GPS with an accuracy circle; works when permission is denied (search or drag the pin); the pin is always adjustable; coordinates are validated on the server | Must | Done |
| FR-06 | Photo EXIF/GPS metadata is stripped before storage | Must | Done |
| FR-07 | Reports of the same category within **25 m and 7 days** merge into one cluster | Must | Done |
| FR-08 | **3+ same-category reports within 50 m in 30 days** make a hotspot | Must | Done |
| FR-09 | Admin dashboard: KPIs, map, filterable report list, photo, status change (pending → in progress → resolved) with history, hotspots | Must | Done |
| FR-10 | Only admins (server-checked custom claim) can change status or view photos | Must | Done |
| FR-11 | Citizen sees their report's status via its ID ("My reports" on the device) | Should | Done |
| FR-12 | Blank photos and photos of people or animals **can't be reported**; a dialog explains why and asks for a retake | Must | Done |
| FR-13 | "AI found nothing" reports need a ≥ 15-character description, are marked **ai_rejected**, are limited to 2 per hour per user, and never count toward hotspots | Should | Done |
| FR-14 | If the phone couldn't reach the AI, the server re-runs the AI on the photo when the report arrives | Should | Done |
| FR-15 | Reused photos: the same person can't send the same photo twice; another person's reuse is grouped within 25 m and rejected further away; this works across resizing and recompression | Should | Done |
| FR-16 | Admin list sorted by priority (AI-verified → unverified → AI found nothing) | Should | Done |
| FR-17 | Android APK + installable web app (PWA / iPhone "Add to Home Screen") | Should | Done |
| FR-18 | Demo with staged dataset photos only (the bundled sample photos) | Must | Done |

## Non-functional requirements

| ID | Category | Requirement | Target | How measured | Result |
|----|----------|-------------|--------|--------------|--------|
| NFR-01 | Performance | AI analysis time per photo, end to end through the public tunnel | ≤ 10 s | 3 timed `/classify` calls through the tunnel, 1920×2560 photo, laptop i5-1235U (2026-11-10) | 3.3–4.4 s |
| NFR-02 | Performance | Model inference alone | ≤ 3 s | `tools/eval_models.py` | ~1.6 s |
| NFR-03 | Accuracy / safety | Irrelevant photos (blank, people) confidently suggested as an issue | 0 | `tools/eval_decisions.py` on `eval/set1` | 0 / 12 (animals not yet in set) |
| NFR-04 | Accuracy | Garbage photos given the right suggestion | ≥ 80% | same | 15 / 17 (88%) |
| NFR-05 | Accuracy | Pothole photos given the right suggestion | ≥ 60% | same | 16 / 23 (70%); only 8 confident |
| NFR-06 | Security | Status changes and photos need an admin token, checked on the server | 100% of tests | pytest + live smoke | pass |
| NFR-07 | Security / abuse | Rate limits: 5 reports / 10 min per user, 20 / hour per IP, 30 analyses / 10 min, 2 "AI found nothing" / hour | enforced | pytest rate-limit tests | pass |
| NFR-08 | Privacy | Stored photos contain no EXIF/GPS | 100% | pytest (real GPS EXIF fixture) + live smoke | pass |
| NFR-09 | Cost | Monthly running cost | ₨0 (free plans only) | Firebase Spark, Cloudflare quick tunnel, Esri basemap | ₨0 |
| NFR-10 | Robustness | Bad input is rejected with a clear error (oversize, wrong type, corrupt, decompression bomb, bad coordinates) | 100% of cases | pytest input tests | pass |
| NFR-11 | Availability | Public API reconnects after a network drop without manual action | ≤ 3 min | watchdog in `tools/serve_public.py` (manual observation) | reconnected automatically after Wi-Fi drops on 2026-11-10 |
| NFR-12 | Usability | Time for a first-time user to send a report | ≤ 60 s | manual walkthrough with sample photo | ~30 s |

## Constraints

- **Free plans only:** Firebase Spark, no paid hosting, no card on file.
- **Pretrained models only,** with verified licences (AGPL-3.0 / MIT). There's no training.
- **Photo only:** no live video.
- **Keys and secrets stay on the server**; the client holds only public Firebase config.
- **Demo uses staged images only.**

## Assumptions

- Citizens have a smartphone with a camera and mobile data.
- A single laptop can serve the pilot's AI load (one photo at a time, about 2 s each).
- Admin accounts are created by the project team (no self-sign-up).

## Out of scope

- Citizen accounts and profiles
- Push or SMS notifications
- Live video detection
- Real integration with, or claims of connection to, any authority
- Training or fine-tuning models
- Production hosting with an SLA for the AI service
