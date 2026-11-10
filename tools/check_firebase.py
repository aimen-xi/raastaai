"""Health check of the Firebase project setup. Creates and deletes one throwaway anonymous user.

Usage: python tools/check_firebase.py
"""
import json
import os
import urllib.error
import urllib.request

import firebase_admin
from firebase_admin import auth, credentials, firestore

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = json.load(open(os.path.join(ROOT, "config", "firebase-web.json"), encoding="utf-8"))
IDT = "https://identitytoolkit.googleapis.com/v1/accounts:"


def post(method, body):
    req = urllib.request.Request(f"{IDT}{method}?key={CFG['apiKey']}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, json.loads(e.read()).get("error", {}).get("message")
    except Exception as e:  # network
        return None, f"network: {e}"


def main():
    firebase_admin.initialize_app(credentials.Certificate(os.path.join(ROOT, "secrets", "firebase-admin.json")))
    ok, err = post("signUp", {"returnSecureToken": True})
    if ok:
        print("Anonymous sign-in: ENABLED")
        auth.delete_user(ok["localId"])
    else:
        print("Anonymous sign-in: NOT OK ->", err)
    _, err = post("signInWithPassword", {"email": "probe@example.invalid", "password": "not-a-real-pass", "returnSecureToken": True})
    if err in ("EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS", "INVALID_PASSWORD"):
        print("Email/Password sign-in: ENABLED")
    else:
        print("Email/Password sign-in: NOT OK ->", err)
    users = [u for u in auth.list_users().iterate_all() if u.email]
    print("Email users:", [(u.email, bool((u.custom_claims or {}).get("admin"))) for u in users] or "none")
    db = firestore.client()
    ref = db.collection("_healthcheck").document("ping")
    ref.set({"ok": True})
    print("Firestore write/read via Admin SDK:", ref.get().to_dict())
    ref.delete()


if __name__ == "__main__":
    main()
