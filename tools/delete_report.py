"""Delete test reports (report + its image; its cluster too when it was the only member).

Usage: python tools/delete_report.py RA-XXXXXX [RA-YYYYYY ...]
"""
import os
import sys

import firebase_admin
from firebase_admin import credentials, firestore

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main(ids):
    firebase_admin.initialize_app(credentials.Certificate(os.path.join(ROOT, "secrets", "firebase-admin.json")))
    db = firestore.client()
    for rid in ids:
        ref = db.collection("reports").document(rid)
        snap = ref.get()
        if not snap.exists:
            print(rid, "not found")
            continue
        cid = snap.to_dict().get("clusterId")
        others = [d for d in db.collection("reports").where("clusterId", "==", cid).stream() if d.id != rid] if cid else []
        ref.delete()
        db.collection("reportImages").document(rid).delete()
        if cid and not others:
            db.collection("clusters").document(cid).delete()
            print(rid, "deleted with cluster", cid)
        else:
            if cid:
                db.collection("clusters").document(cid).update({"reportCount": firestore.Increment(-1)})
            print(rid, "deleted;", len(others), "report(s) remain in", cid)


if __name__ == "__main__":
    main(sys.argv[1:])
