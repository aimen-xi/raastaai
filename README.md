# RaastaAI

> AI-Powered SE-MAX · CUI Tech Fest FA'26 · Team: <Team Name>
>
> **Pilot concept.** Not connected to any government authority.

## What it does

Citizens report a **pothole** or a **garbage pile** with one photo. An AI model *suggests* what the photo shows, and the citizen confirms it and drops a pin. Admins see grouped reports, hotspots and photos on a dashboard, and update each report's status.

## Problem and user

- **Citizens** see broken roads and dumped garbage every day, but have no quick, low-effort way to report them with proof and an exact location.
- **City / municipal staff** (the admins in this pilot) get scattered, duplicate complaints with no photos or coordinates, so they can't prioritise.

RaastaAI makes a report take about 30 seconds and turns many reports into a short, ranked list of real problems:
- duplicates within 25 m are merged;
- spots with 3 or more reports become hotspots;
- reports the AI has verified are shown first.

## Live deployment

- **Citizen app (web):** https://raastaai-citizen.web.app
- **Citizen app (Android APK):** https://github.com/aimen-xi/raastaai/releases/latest/download/RaastaAI.apk
- **Admin dashboard:** https://rastaai-e99f8.web.app
- **Platform:**
  - Flutter (Android + web) for the citizen app.
  - React + Vite for the admin dashboard.
  - Both are hosted on Firebase Hosting.
  - The FastAPI + ONNX AI service runs on a laptop and is exposed through a free Cloudflare tunnel (see [Known limitations](#known-limitations)).

### Install the Android app (APK)

1. On an Android phone, open the [latest release](https://github.com/aimen-xi/raastaai/releases/latest) and tap **RaastaAI.apk**. The file is about 20 MB and is built for 64-bit ARM phones (Android 7+).
2. When the download finishes, tap the file. If Android says installs from this source aren't allowed, tap **Settings → Allow from this source**, then go back.
3. Tap **Install**. If Play Protect warns about an unrecognised app, tap **More details → Install anyway**. The app isn't on the Play Store; it's a demo build.
4. Open **RaastaAI** and allow location when asked. Denying is fine too: you can place the pin by hand.

**iPhone:** open https://raastaai-citizen.web.app in Safari → **Share → Add to Home Screen**. It opens full-screen like an app.

## Judge quick start (under 5 minutes)

1. On a phone or browser, open **https://raastaai-citizen.web.app**, or install the APK above.
   - To install the APK on Android, allow installs from your browser when asked.
2. Tap **Try a sample photo → Pothole**.
   - The AI outlines the pothole and shows its confidence.
   - Tap **Confirm & set location**. Allow location, or deny it and drag the map pin instead.
   - Tap **Use this location → Submit report** and note the report ID (RA-XXXXXX).
3. Check the edge cases:
   - Report the same sample again from another spot: sample photos are allowed to repeat.
   - Upload a **blank photo** or a **photo of a person**: a dialog explains that it can't be reported.
   - Upload a **plain photo with no issue**: you can only report it with a description, and it's marked "AI found nothing".
4. Open **https://rastaai-e99f8.web.app** and sign in with the judge test account below.
   - Find your report in **Reports**. It's sorted AI-verified first.
   - Open the photo (the stored copy has EXIF removed).
   - Change its status to **In progress**.
   - Open the **Hotspots** tab.
5. Back in the citizen app, open **My reports**: the new status shows there.

## Test accounts

| Role | Username / email | Password |
|------|------------------|----------|
| Admin (judge) | `<judge test account>` | `<shared with organisers>` |
| Citizen | none needed: anonymous sign-in happens automatically | none |

<!-- Test accounts only. Never real credentials. Create one with the Firebase console + `python tools/set_admin.py grant <email>`. -->

## Run locally

### Prerequisites

- Python 3.11+
- Node.js 22+
- Flutter (stable; Dart ≥ 3.13)
- Firebase CLI (`npm i -g firebase-tools`)
- `cloudflared` (only for a public URL)
- A Firebase project on the free **Spark** plan with:
  - Anonymous and Email/Password sign-in;
  - Firestore;
  - Hosting.

### Setup

```bash
python -m venv .venv
```
```bash
.venv/Scripts/python -m pip install -r api/requirements-dev.txt
```
```bash
npm ci --prefix admin
```
```bash
cd app && flutter pub get
```

1. **AI models.** They're not in git: one is 104 MB, over GitHub's file limit.
   - Download the three checkpoints listed in `api/models/models.json`:
     - [FarzadNekouee pothole YOLOv8n-seg](https://github.com/FarzadNekouee/YOLOv8_Pothole_Segmentation_Road_Damage_Assessment);
     - [turhancan97 trash YOLOv8m-seg](https://huggingface.co/turhancan97/yolov8-segment-trash-detection);
     - Ultralytics COCO YOLOv8n.
   - Put them in `api/models/raw/`.
   - Run `python tools/export_models.py api/models/raw api/models`. This needs `pip install ultralytics`, and only converts the models; there's no training.
2. **Firebase.**
   - Save a service-account key as `secrets/firebase-admin.json`. It's git-ignored and never committed.
   - Deploy the rules and indexes:
     ```bash
     firebase deploy --only firestore
     ```
3. **Admin user.** Create an Email/Password user in the Firebase console, then run:
   ```bash
   python tools/set_admin.py grant <email>
   ```

### Environment variables

The names are listed in [`.env.example`](.env.example). Values go in a local `.env` or your shell, never in git.

| Part | Variables |
|---|---|
| API | `TICKET_SECRET`, `IP_HASH_SALT`, `FIREBASE_KEY_PATH` / `FIREBASE_SERVICE_ACCOUNT_JSON`, `ALLOWED_ORIGINS`, `STORE`, `MODEL_DIR`, `MODEL_THREADS` |
| Admin dashboard | `VITE_API_BASE` (optional) |
| Citizen app | `--dart-define=API_BASE=...` (optional), `--dart-define=DEMO_SAMPLES=true/false` |

### Run

On Windows, double-click **`start_server.bat`** in the project folder. Or run:

```bash
.venv/Scripts/python tools/serve_public.py
```

This one command:
- starts the API on `127.0.0.1:7860`;
- opens a Cloudflare quick tunnel;
- publishes the tunnel URL to Firestore `public/config`. Both apps read it at runtime.

While it runs:
- If the tunnel drops (for example a Wi-Fi blip), it reconnects and publishes the new URL.
- If the API crashes, it restarts on the same port. After 4 crashes in 10 minutes it stops and shows the error.
- Windows is kept from sleeping. This changes no power settings and ends when the window closes. Closing the lid can still sleep the laptop, so keep it open during the demo.
- Starting it twice is refused, so two copies never fight over the port.

To check it's up, open `<tunnel URL>/health` in a browser. The window prints the URL.

To run the apps locally against it:

```bash
npm run dev --prefix admin
```
```bash
cd app && flutter run -d chrome
```

To deploy the web apps:

```bash
npm run build --prefix admin
```
```bash
cd app && flutter build web --release
```
```bash
firebase deploy --only hosting
```

To build the Android APK:

```bash
cd app && flutter build apk --release --target-platform android-arm64
```

### Run tests

```bash
bash scripts/test.sh
```

This runs the API pytest suite, the admin vitest + lint + build, and Flutter analyze + test. CI runs the same script on every push and pull request.

Two more suites run separately:

```bash
firebase emulators:exec --only firestore "npm --prefix firebase/rules-tests test"
```
```bash
.venv/Scripts/python tools/smoke_live.py
```

- **Rules tests:** the first command runs the Firestore security-rules tests on the emulator.
- **Live smoke test:** the second runs 12 checks against the real Firebase project. It deletes everything it creates.

See [docs/testing.md](docs/testing.md).

## Known limitations

- **The AI service runs on a laptop**, behind a free Cloudflare quick tunnel.
  - We found no free host that fits the API (about 1.1 GB of memory with the three models loaded).
    - Hugging Face now needs a paid PRO plan to run Docker or Gradio Spaces.
    - Render's free tier has 512 MB of memory.
    - The team rule is free plans only.
  - The websites and database are hosted, but photo analysis and report submission need that laptop online.
  - The tunnel URL changes when the server restarts; the apps pick up the new one automatically.
- **Pothole detection is weaker on out-of-domain photos.**
  - On our 56-image evaluation set, 16 of 23 potholes got the right suggestion, but only 8 were confident.
  - Uncertain results always ask the citizen, and a manual category is always allowed. See [docs/testing.md](docs/testing.md#measured-metrics).
- **The evaluation set is small** (56 images). It checks the decision rules; it isn't a benchmark.
- **No citizen accounts:** sign-in is anonymous, so "My reports" lives on the device.
- **Not included:** notifications, live video, and real integration with authorities. They're out of scope for the pilot.
- **Map tiles** come from Esri's free World Street Map, which needs no key.
- **The release APK is signed with a debug key.** It's for demo installs only, not the Play Store.

## Documentation

- [Requirements](docs/requirements.md)
- [Design](docs/design.md)
- [Testing](docs/testing.md)
- [AI usage log](docs/ai-usage-log.md)
- [Judge checks](docs/judge-checks.md)
- Background: [scope v2](docs/SCOPE_v2.md), [audit and plan](docs/AUDIT_AND_PLAN.md), [model evaluation](docs/MODEL_EVAL.md), [account setup](docs/SETUP_ACCOUNTS.md)

## Licence

[AGPL-3.0](LICENSE). The project uses Ultralytics YOLOv8 models, which are AGPL-3.0.

## Team

| Name | Role |
|------|------|
|      |      |
