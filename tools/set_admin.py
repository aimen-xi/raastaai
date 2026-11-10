"""Grant or list the `admin` custom claim (dashboard access) with the Firebase Admin SDK.

Usage:
  python tools/set_admin.py list                 # list email users and their admin flag
  python tools/set_admin.py grant <email>         # set admin=true
  python tools/set_admin.py revoke <email>        # remove admin
Reads the service-account key from secrets/firebase-admin.json (never committed).
The user must sign out and in again (or refresh the ID token) for a change to apply.
"""
import os
import sys

import firebase_admin
from firebase_admin import auth, credentials

KEY = os.path.join(os.path.dirname(__file__), "..", "secrets", "firebase-admin.json")


def main(cmd, email=None):
    firebase_admin.initialize_app(credentials.Certificate(KEY))
    if cmd == "list":
        for u in auth.list_users().iterate_all():
            if u.email:
                print(f"{u.email}  admin={bool((u.custom_claims or {}).get('admin'))}  uid={u.uid}")
        return
    user = auth.get_user_by_email(email)
    claims = dict(user.custom_claims or {})
    if cmd == "grant":
        claims["admin"] = True
    elif cmd == "revoke":
        claims.pop("admin", None)
    else:
        raise SystemExit(f"unknown command {cmd}")
    auth.set_custom_user_claims(user.uid, claims or None)
    print(f"{email}: admin={claims.get('admin', False)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
