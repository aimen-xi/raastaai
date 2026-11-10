"""Run the RaastaAI API on this laptop and expose it through a free Cloudflare quick tunnel.

  python tools/serve_public.py

1. starts the API (uvicorn, real models, real Firestore) on 127.0.0.1:7860
2. starts `cloudflared tunnel --url ...` and reads the public https://*.trycloudflare.com address
3. waits until /health answers through the tunnel
4. writes that address to the public Firestore doc `public/config`, which both apps read at startup
Keep the window open during the demo; Ctrl+C stops everything. Re-running gives a new address and
the apps pick it up automatically (no rebuild, no redeploy).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe") if os.name == "nt" else sys.executable
PORT = 7860
RUNTIME = os.path.join(ROOT, "secrets", "runtime.json")
ORIGINS = [
    "https://rastaai-e99f8.web.app", "https://rastaai-e99f8.firebaseapp.com",
    "https://raastaai-citizen.web.app", "https://raastaai-citizen.firebaseapp.com",
    "http://localhost:5500", "http://localhost:5173",
]


def cloudflared() -> str:
    for p in (shutil.which("cloudflared"), r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
              r"C:\Program Files\cloudflared\cloudflared.exe"):
        if p and os.path.exists(p):
            return p
    sys.exit("cloudflared not found. Install it:  winget install --id Cloudflare.cloudflared -e")


def runtime_secrets() -> dict:
    """Ticket secret + IP salt, generated once and kept in secrets/ (gitignored) so restarts don't
    invalidate classification tickets in flight."""
    if os.path.exists(RUNTIME):
        return json.load(open(RUNTIME))
    data = {"TICKET_SECRET": secrets.token_urlsafe(48), "IP_HASH_SALT": secrets.token_urlsafe(24)}
    json.dump(data, open(RUNTIME, "w"))
    return data


def get(url: str, timeout=10) -> int:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "raasta-serve"}), timeout=timeout) as r:
            return r.status
    except Exception:
        return 0


def publish(api_base: str):
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(os.path.join(ROOT, "secrets", "firebase-admin.json")))
    firestore.client().collection("public").document("config").set(
        {"apiBase": api_base, "updatedAt": datetime.now(timezone.utc)})


def main():
    env = dict(os.environ, ALLOWED_ORIGINS=",".join(ORIGINS), **runtime_secrets())
    api = subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--app-dir", "api", "--host", "127.0.0.1",
                            "--port", str(PORT), "--no-access-log"], cwd=ROOT, env=env)
    print("Starting API (loading models)...", flush=True)
    for _ in range(120):
        if get(f"http://127.0.0.1:{PORT}/health", 3) == 200:
            break
        if api.poll() is not None:
            sys.exit("API failed to start (is port 7860 already in use?)")
        time.sleep(1)
    print("API ready on http://127.0.0.1:%d" % PORT, flush=True)

    tun, url = open_tunnel()
    if url:
        go_live(url)
    else:
        tun.kill()
        print("Could not open a Cloudflare tunnel yet (internet down?); retrying every 30 s.", flush=True)
    # Watchdog: if the tunnel dies or the public URL stops answering for ~2 minutes (Wi-Fi drop),
    # open a fresh tunnel and publish the new address. Both apps re-read it on their next request.
    fails = 0
    try:
        while api.poll() is None:
            time.sleep(30)
            ok = bool(url) and tun.poll() is None and get(f"{url}/health", 15) == 200
            fails = 0 if ok else fails + 1
            if fails >= 4 or tun.poll() is not None:
                print("Tunnel not answering - reconnecting...", flush=True)
                if tun.poll() is None:
                    tun.terminate()
                new_tun, new_url = open_tunnel()
                if new_url:
                    tun, url, fails = new_tun, new_url, 0
                    go_live(url)
                else:
                    new_tun.kill()
                    print("Still offline; will retry in 30 s.", flush=True)
        print("The API process exited. Re-run this script.", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (tun, api):
            if p.poll() is None:
                p.terminate()


def open_tunnel():
    """Start a quick tunnel over HTTP/2 (TCP 443; steadier than QUIC/UDP on home and mobile
    networks) and return (process, public url or None)."""
    tun = subprocess.Popen([cloudflared(), "tunnel", "--no-autoupdate", "--protocol", "http2",
                            "--url", f"http://127.0.0.1:{PORT}"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    box = {}
    found = threading.Event()

    def pump():
        for line in tun.stdout:
            m = re.search(r"https://([a-z0-9-]+)\.trycloudflare\.com", line)
            if m and m.group(1) != "api" and "url" not in box:  # api.* is cloudflared's own endpoint
                box["url"] = m.group(0)
                found.set()
            if "ERR" in line and "Unauthorized" not in line:
                print("[tunnel]", line.strip(), flush=True)

    threading.Thread(target=pump, daemon=True).start()
    found.wait(60)
    return tun, box.get("url")


def go_live(url: str):
    print("Tunnel:", url, "- waiting for it to go live...", flush=True)
    for _ in range(60):
        if get(f"{url}/health") == 200:
            break
        time.sleep(2)
    else:
        # never publish an address that doesn't answer: the watchdog will try a fresh tunnel
        print("Tunnel did not answer; not publishing it.", flush=True)
        return
    publish(url)
    print("\n  PUBLIC API:  %s\n  Published to Firestore public/config - the apps will use it automatically.\n"
          "  Keep this window open. Ctrl+C to stop.\n" % url, flush=True)

if __name__ == "__main__":
    main()
