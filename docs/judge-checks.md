# Judge checks

Each check from the judges' review, with where it's implemented and where it's tested.

| # | Judge check | Implemented in | Tested by | Try it live |
|---|---|---|---|---|
| 1 | Pretrained models with verified licences | `api/models/models.json` (sources, SHA-256), `tools/export_models.py`, `tools/inspect_pickle.py` | `api/tests/test_real_models.py`, [MODEL_EVAL.md](MODEL_EVAL.md) | — |
| 2 | Photo only (no video) | `app/lib/screens/home.dart` (camera / gallery single image) | manual | Citizen app home |
| 3 | AI never auto-creates a report; uncertain / not-an-issue outcomes; the user confirms | `api/app/decide.py`, `api/app/main.py` (`/classify` creates nothing, HMAC ticket), `app/lib/screens/result.dart` | `test_classify_returns_suggestion_and_creates_nothing`, ticket tests, `test_manual_fallback_when_ai_unavailable` | Sample photo → result screen |
| 4 | Irrelevant photos (people, animals, blank) not accepted | `decide.py` (blank + COCO gate), `reports.py` (`HARD_REJECT`), retake dialog in `result.dart` | `test_real_models.py`, `test_blank_or_person_photo_cannot_be_reported` | Upload a blank photo |
| 5 | Location: permission denied handled, pin adjustable, coordinates validated | `app/lib/screens/location.dart`, `api/app/geo.py` (`parse_coords`) | `test_location_denied_manual_pin_works`, `test_bad_coordinates_400`, `test_outside_pakistan_flagged_not_rejected` | Deny location → drag pin |
| 6 | Strip EXIF; demo only with staged images | `api/app/images.py` (`clean_for_storage`), `app/assets/samples/` (+ `CREDITS.txt`) | `test_stored_image_has_no_exif_or_gps`, `test_admin_image_endpoint_also_clean`, live smoke | Admin photo view |
| 7 | Tested merge and hotspot rules | `api/app/clustering.py`, `api/app/reports.py` | merge, hotspot and expiry tests (see [testing.md](testing.md) EC-15/16) | Admin → Hotspots |
| 8 | Server-side admin protection | `api/app/security.py` (`require_admin`), `firebase/firestore.rules` | `test_status_change_requires_admin`, `test_no_token_is_401`, `firebase/rules-tests` | Citizen can't change status |
| 9 | Rate limits | `api/app/ratelimit.py`, `api/app/config.py` | `test_sixth_report_in_10_min_is_429`, IP and spoofing tests, `test_classify_rate_limit`, override limit | — |
| 10 | Keys server-side; manual fallback | `secrets/` (git-ignored), `.env.example`, `api/app/main.py` startup guard; fallback in `analysing.dart` / `result.dart` | `test_manual_fallback_when_ai_unavailable`, `test_server_rechecks_when_phone_could_not_reach_ai` | — |
| 11 | Cuts: no live video, no citizen accounts, no notifications, no claims of connecting to authorities | Scope ([SCOPE_v2.md](SCOPE_v2.md) §8); "Pilot concept" banners in both apps | manual review | Footer / login page |
| 12 | Bad input handled | `api/app/images.py`, `api/app/main.py` | 413 / 415 / corrupt / bomb / missing-field tests | Upload a PDF |
| 13 | Duplicate / reused photos (our addition) | `api/app/images.py` (dHash), `reports.py` (`check_photo_reuse`) | duplicate-photo tests, live smoke | Send the same photo twice |
