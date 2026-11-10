# Testing

## Test strategy

- **Business rules are pure functions or transactional code, tested in-process.**
  - This covers clustering, hotspots, rate limits, verification tiers and photo reuse.
  - The API tests use FastAPI's `TestClient` with an in-memory store and a fake classifier.
  - The same `Tx` interface runs on Firestore in production, so the tests exercise the real code paths.
- **Real-model tests** (`api/tests/test_real_models.py`) run the actual ONNX models on blank images, people and clean roads. They skip when the models aren't on disk (as in CI).
- **The Firestore security rules** are tested on the Firebase emulator.
- **The admin dashboard logic** (filters, priority sort, KPIs, hotspot areas) is unit-tested with vitest. Its TypeScript build and lint are part of the suite.
- **The citizen app's API client** (parsing, error mapping, form fields) is tested with mocked HTTP. `flutter analyze` must report no issues.
- **A live smoke test** (`tools/smoke_live.py`) runs the judge flows against the **real** Firebase project and deletes everything it creates.
- **Manual end-to-end:** the citizen flow on an Android phone (APK) and on the web, plus the admin flow on the hosted dashboard.

## How to run tests

```
bash scripts/test.sh
```

On Windows, use `PYTHON=.venv/Scripts/python.exe bash scripts/test.sh`. That runs the API pytest, admin vitest + oxlint + tsc build, and Flutter analyze + test. CI runs the same script on every push and pull request.

Two more suites run separately:

```
firebase emulators:exec --only firestore "npm --prefix firebase/rules-tests test"
```
```
.venv/Scripts/python tools/smoke_live.py
```

- The first runs the Firestore rules tests (needs Java + the Firebase CLI).
- The second runs the live smoke test (needs `secrets/firebase-admin.json` + the models).

## Results summary

These results are from 2026-11-10, on the laptop with the models present.

| Type | Total | Passed | Failed |
|------|-------|--------|--------|
| Unit: API rules + real models (pytest) | 52 | 52 | 0 |
| Unit: admin logic (vitest) | 9 | 9 | 0 |
| Unit: citizen API client (flutter test) | 5 | 5 | 0 |
| Integration: Firestore security rules (emulator) | 6 | 6 | 0 |
| Integration: live smoke against real Firebase | 12 | 12 | 0 |
| End-to-end / manual (phone APK + web + admin) | see below | team-verified | 0 open |

The team walked through these flows manually on an Android phone (APK), the citizen website and the admin dashboard, and reported them working on 2026-11-10:
- a pothole sample report;
- a garbage sample report;
- location permission denied, with the pin dragged by hand;
- a blank photo, which showed the retake dialog;
- a no-issue photo, which needed a description;
- a duplicate photo;
- an admin status change, with the status visible in "My reports";
- the hotspots tab;
- the map tiles in both apps.

In CI the 10 real-model tests skip, because the models aren't committed (see the README).

## Edge cases covered

| ID | Edge case | Expected behaviour | Test / evidence | Result |
|----|-----------|--------------------|-----------------|--------|
| EC-01 | File > 8 MB | 413, clear message | `test_huge_file_rejected_413` | Pass |
| EC-02 | PDF renamed `.jpg` | 415 (type checked by content) | `test_non_image_rejected_415_even_if_named_jpg` | Pass |
| EC-03 | Truncated / corrupt JPEG | 400 | `test_truncated_jpeg_rejected_400` | Pass |
| EC-04 | Decompression bomb | Rejected | `test_decompression_bomb_rejected` | Pass |
| EC-05 | Missing image / fields, bad coordinates, bad category, note too long | 400 with field name | `test_missing_image_400`, `test_missing_fields_400`, `test_bad_coordinates_400`, `test_bad_category_and_note` | Pass |
| EC-06 | Photo has GPS EXIF | Stored copy has no EXIF; admin image endpoint also clean | `test_stored_image_has_no_exif_or_gps`, `test_admin_image_endpoint_also_clean`, live smoke | Pass |
| EC-07 | Location permission denied | Manual pin works, no accuracy stored | `test_location_denied_manual_pin_works`, live smoke | Pass |
| EC-08 | Pin outside Pakistan | Accepted but flagged | `test_outside_pakistan_flagged_not_rejected` | Pass |
| EC-09 | Classify creates a report? | Never | `test_classify_returns_suggestion_and_creates_nothing` | Pass |
| EC-10 | Forged / other-photo / wrong-secret AI ticket | Ignored | `test_tampered_or_foreign_ticket_is_ignored` | Pass |
| EC-11 | AI down | Manual category, unverified | `test_manual_fallback_when_ai_unavailable` | Pass |
| EC-12 | Phone couldn't reach the AI, but the photo is a real pothole | Server re-checks → verified | `test_server_rechecks_when_phone_could_not_reach_ai`, live smoke | Pass |
| EC-13 | Blank photo / photo of a person | Can't be reported (422); app shows a retake dialog | `test_blank_or_person_photo_cannot_be_reported`, real-model tests, manual | Pass |
| EC-14 | "AI found nothing" sent anyway | Needs ≥ 15-char note → ai_rejected; max 2/hour; never a hotspot | `test_no_issue_override_needs_a_note_and_is_ai_rejected`, `test_no_issue_overrides_limited_to_two_per_hour`, `test_ai_rejected_reports_never_make_a_hotspot` | Pass |
| EC-15 | Same spot reported twice | Merged (25 m / 7 days, same category) | `test_same_spot_merges`, `test_far_or_other_category_does_not_merge`, `test_merge_window_expires_after_7_days`, `test_merge_across_geohash_cell_boundary` | Pass |
| EC-16 | Hotspot | 3 within 50 m in 30 days; expires | `test_hotspot_after_three_reports_within_50m`, `test_no_hotspot_when_older_than_30_days` | Pass |
| EC-17 | Same photo, same person, twice (double tap) | 409 duplicate_report | `test_same_person_same_photo_twice_is_a_duplicate`, live smoke | Pass |
| EC-18 | Same photo (WhatsApp-resized) by another person, same spot / far away | Grouped + flagged / 409 photo_reused | `test_same_photo_other_person_same_spot_is_grouped_and_marked`, `test_same_photo_other_person_other_place_is_rejected`, `test_dhash_survives_resize_and_recompression` | Pass |
| EC-19 | Bundled demo sample reused by many judges | Allowed, marked demo photo | `test_bundled_demo_samples_may_be_reused` | Pass |
| EC-20 | Citizen calls the admin status endpoint | 403; no token → 401 | `test_status_change_requires_admin`, `test_no_token_is_401`, rules tests | Pass |
| EC-21 | 6th report in 10 min; new anonymous users from one IP; spoofed `X-Forwarded-For` | 429 | `test_sixth_report_in_10_min_is_429`, `test_ip_limit_applies_across_new_anonymous_users`, `test_spoofed_forwarded_for_does_not_bypass_ip_limit`, `test_classify_rate_limit` | Pass |
| EC-22 | Public status leaks location? | No | `test_public_status_reveals_no_location` | Pass |

## Measured metrics

| Metric | Method | Result |
|--------|--------|--------|
| Irrelevant photos (blank 6, people 2) confidently called an issue | `tools/eval_decisions.py` on `eval/set1` (56 images) | **0 / 12** (clean roads: 3 of 4 not_issue, 1 uncertain) |
| Garbage: correct suggestion | same | 15 / 17 (14 confident) |
| Pothole: correct suggestion | same | 16 / 23, **only 8 confident** (weak spot: out-of-domain rural photos) |
| Garbage model bake-off | `tools/eval_models.py` | turhancan P 0.75 / R 0.75 vs kendrickfff P 0.57 / R 0.25 |
| ONNX runtime parity with Ultralytics | same input, max-confidence difference | 0.0000 |
| Inference time per photo | laptop i5-1235U, 2 threads | ~1.6 s |
| `/classify` through the public tunnel | 3 calls, 1920×2560 JPEG (398 KB) | 3.3–4.4 s |
| APK download through the tunnel | 20 MB | ~60 s (laptop upload speed) |

Details: [MODEL_EVAL.md](MODEL_EVAL.md). The evaluation set is small; these numbers show the rules work as designed, not general accuracy.

## Defect log

| ID | Description | Found by / how | Severity | Status | Fix commit |
|----|-------------|----------------|----------|--------|------------|
| D-01 | Phone photos analysed sideways (EXIF orientation ignored) → low recall | Model evaluation | High | Fixed | `feat/api` import |
| D-02 | Linear downscale of 12 MP photos cut pothole recall 0.69 → 0.38 | Model evaluation | High | Fixed (INTER_AREA) | `feat/api` import |
| D-03 | Litter model fired on clothing, so people photos became "garbage" | Model evaluation | High | Fixed (COCO person/animal gate first) | `feat/api` import |
| D-04 | Admin map tiles grey until resize | Manual test | Medium | Fixed (ResizeObserver + invalidateSize) | `feat/admin-dashboard` import |
| D-05 | Leaflet controls drawn over the admin header | Manual test | Low | Fixed (z-index / isolation) | `feat/admin-dashboard` import |
| D-06 | Same hotspot listed twice | Manual test | Medium | Fixed (`hotspotAreas`) | `feat/admin-dashboard` import |
| D-07 | Phone GPS gave up after 15 s indoors; pin left at the default city | User test on phone | High | Fixed (30 s + last known position) | `feat/citizen-app` import |
| D-08 | Map "Access blocked" (OSM: no referrer), then "API key required" (CARTO) | User test | High | Fixed (Esri tiles, referrer policy) | `feat/citizen-app`, `feat/admin-dashboard` imports |
| D-09 | Tunnel died on Wi-Fi drops; published Cloudflare's own `api.` URL once | User report + logs | High | Fixed (HTTP/2, watchdog, never publish an address that doesn't answer) | `chore/tools-and-eval` import |
| D-10 | Random photo + manual category could flood reports | User review | High | Fixed (FR-12 to FR-14) | `feat/api` import |
| D-11 | Same photo could be reused at other locations | User review | High | Fixed (FR-15) | `feat/api` import |

## Known untested areas

- Animal photos (none in the evaluation set yet; covered by the COCO gate but not measured).
- iPhone (Safari "Add to Home Screen") has not been tested on a real iPhone.
- Load or concurrency beyond a few users (the models run one photo at a time by design).
- The Firestore rules tests run only locally (they need the emulator), not in CI.
