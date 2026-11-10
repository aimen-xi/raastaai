#!/usr/bin/env bash
# Runs every automated test suite in the repo. Used by CI (.github/workflows/ci.yml) and locally.
# Each part runs only if its folder exists, so the script works at every commit.
#
# Local use (Windows, Git Bash):  PYTHON=.venv/Scripts/python.exe bash scripts/test.sh
# Skip a part:                    SKIP_FLUTTER=1 bash scripts/test.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python}"
failed=0
section() { printf '\n========== %s ==========\n' "$1"; }

# --- API (FastAPI): unit + API tests. Real-model tests skip when api/models/*.onnx are absent (CI).
if [ -d api ] && [ -z "${SKIP_API:-}" ]; then
  section "API (pytest)"
  if [ -n "${CI:-}" ]; then "$PYTHON" -m pip install -q -r api/requirements-dev.txt; fi
  "$PYTHON" -m pytest api/tests -q || failed=1
fi

# --- Admin dashboard (React + Vite): unit tests, lint, type-check + build
if [ -d admin ] && [ -z "${SKIP_ADMIN:-}" ]; then
  section "Admin dashboard (vitest, oxlint, tsc)"
  if [ -n "${CI:-}" ] || [ ! -d admin/node_modules ]; then npm ci --prefix admin --no-audit --no-fund; fi
  npm test --prefix admin || failed=1
  npm run lint --prefix admin || failed=1
  npm run build --prefix admin || failed=1
fi

# --- Citizen app (Flutter): static analysis + widget/unit tests
if [ -d app ] && [ -z "${SKIP_FLUTTER:-}" ]; then
  section "Citizen app (flutter analyze, flutter test)"
  if command -v flutter >/dev/null 2>&1; then
    (cd app && flutter pub get >/dev/null && flutter analyze && flutter test) || failed=1
  else
    echo "flutter not installed: skipping (set SKIP_FLUTTER=1 to silence)"; [ -n "${CI:-}" ] && failed=1
  fi
fi

# Firestore security-rules tests need the Firebase emulator (Java); run them separately:
#   firebase emulators:exec --only firestore "npm --prefix firebase/rules-tests test"

if [ "$failed" -ne 0 ]; then echo; echo "SOME TESTS FAILED"; exit 1; fi
echo; echo "ALL TESTS PASSED"
