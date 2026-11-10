# AI Usage Log

Required by the event rules. Log every meaningful use of AI tools during the build.

## Tools used

| Tool | Used for |
|------|----------|
| Claude Code (Claude Opus 5.5, Anthropic), desktop app | Scope audit against the judges' review, architecture, writing and refactoring code (API, Flutter app, admin dashboard, Firebase rules), tests, debugging, build/deploy commands, documentation |
| Pretrained YOLOv8 models (FarzadNekouee pothole-seg, turhancan97 trash-seg, Ultralytics COCO) | Runtime AI inside the product (see [design.md](design.md#ai-components)): no training, no generative AI at runtime |

## Log

| Time | Member | Tool | What it was asked | What was accepted / changed / rejected | How it was verified |
|------|--------|------|-------------------|----------------------------------------|---------------------|
| 2026-11-08 | Aimen Ayub | Claude Code | Audit the scope doc against the judges' review; propose a plan with architect / FE / BE / UI roles and mocks | Accepted the audit and revised scope v2 ([AUDIT_AND_PLAN.md](AUDIT_AND_PLAN.md), [SCOPE_v2.md](SCOPE_v2.md)). **Changed:** no Roboflow, free plans only, OpenStreetMap maps, public garbage model. Mocks reviewed and approved before any code | Team review of each phase before approval |
| 2026-11-09 | Aimen Ayub | Claude Code | Download, licence-check and statically scan pretrained models; export to ONNX; build an evaluation set; calibrate decision rules | Accepted turhancan over kendrickfff (bake-off numbers). Rules in `decide.py` calibrated on `eval/set1`. AI found the EXIF-rotation and resize bugs during evaluation | `tools/eval_models.py`, `tools/eval_decisions.py`, ONNX parity check vs Ultralytics ([MODEL_EVAL.md](MODEL_EVAL.md)) |
| 2026-11-09 | Aimen Ayub | Claude Code | Build the API: validation, EXIF strip, tickets, merge/hotspot, rate limits, admin endpoints | Accepted after review. Every judge check mapped to tests | 42 pytest + live smoke 11/11 against real Firebase |
| 2026-11-09 | Aimen Ayub | Claude Code | Build the Flutter citizen app and React admin dashboard; Firestore rules | Accepted. Several UI bugs found in manual testing and fixed (grey map, header overlap, duplicate hotspot entries, stale cache) | Rules emulator tests, vitest, flutter test, manual walkthrough |
| 2026-11-09 | Aimen Ayub | Claude Code | Deploy the API to a Hugging Face Space | **Rejected / changed:** HF Docker Spaces now need PRO. Team chose laptop + free Cloudflare tunnel; AI wrote `tools/serve_public.py` | Live site tested through the tunnel |
| 2026-11-10 | Aimen Ayub | Claude Code | Build the Android APK; fix phone GPS and the blank map | Accepted. GPS timeout raised + last-known fallback. Map provider changed twice: OSM blocked (missing referrer), CARTO then required a key, Esri now (no key) | Tile images downloaded and checked; team tested on a phone |
| 2026-11-10 | Aimen Ayub | Claude Code | Team found that random photos + manual category could spam reports; asked for a fix | Accepted 4-part design: hard block (blank/person/animal), note-required "AI found nothing" tier, 2/hour limit + no hotspot weight, server re-check | 5 new pytest cases + live API check |
| 2026-11-10 | Aimen Ayub | Claude Code | Team asked: what if one photo is sent from two locations? | Accepted exact + perceptual (dHash) photo matching: duplicate / reused / grouped. **Changed:** demo sample photos exempted so judges can reuse them | 5 new pytest cases + live smoke 12/12 on real Firestore |
| 2026-11-10 | Aimen Ayub | Claude Code | Tunnel drops: diagnose and harden | AI found the root cause (one unreachable Cloudflare IP), added HTTP/2 + watchdog reconnect. **Bug in the AI's own fix:** it once published Cloudflare's `api.trycloudflare.com` as our URL; caught in the logs and fixed | Observed automatic reconnect |
| 2026-11-10 | Aimen Ayub | Claude Code | Set up the repo from the SE-MAX template; write README and docs; CI script | Accepted. Personal data, secrets, large models and people photos kept out of git | `scripts/test.sh` green locally and in CI |

## Reflection

### Where AI helped most

- Turning the judges' review into concrete, testable rules, and writing a test for each one.
- Finding non-obvious bugs from evidence:
  - EXIF rotation feeding sideways photos to the models;
  - a resize method that halved pothole recall;
  - an unreachable Cloudflare edge IP.
- Doing the boring-but-critical parts consistently: input validation, EXIF stripping, rate limits, security rules, docs.

### Where AI was wrong or misleading

- It assumed free hosting options that had changed. Hugging Face Docker Spaces now need PRO, and CARTO map tiles now need a key. Each was found by testing, not by trusting the plan.
- Its first tunnel watchdog published a wrong URL (Cloudflare's own API host), which we caught in the logs.
- Its first location screen gave up on GPS too quickly indoors. Our phone test found it, not the AI.
- It needed the team to spot the product-level abuse cases: random-photo spam, and one photo reported at many places.

### What we did not delegate to AI

- **Product decisions:** scope cuts, free-plans-only, which maps and models to accept, the anti-spam trade-offs.
- **Account actions:** creating accounts, passwords, accepting licences, and approving every phase.
- **Real-world testing** on our own phones, and judging whether results were good enough.
- **What gets published:** what goes public, and under which name.
