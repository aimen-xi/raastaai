"""Create/update the Hugging Face Space that runs the API (free CPU Basic, Docker SDK).

Reads the HF token from secrets/hf_token.txt and the Firebase key from secrets/firebase-admin.json.
Neither is ever printed. Secrets are stored as Space secrets (hidden, not in the repo).

Usage:
  python tools/deploy_space.py <hf-username>            # create Space (if needed), set secrets, upload code+models
  python tools/deploy_space.py <hf-username> --code     # upload code only (secrets untouched)
"""
from __future__ import annotations

import os
import secrets as pysecrets
import sys

from huggingface_hub import HfApi

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPACE_NAME = "raastaai-api"
ORIGINS = [
    "https://rastaai-e99f8.web.app",
    "https://rastaai-e99f8.firebaseapp.com",
    "https://raastaai-citizen.web.app",
    "https://raastaai-citizen.firebaseapp.com",
    "http://localhost:5500",
    "http://localhost:5173",
]


def main():
    user = sys.argv[1]
    code_only = "--code" in sys.argv
    token = open(os.path.join(ROOT, "secrets", "hf_token.txt"), encoding="utf-8-sig").read().strip()
    api = HfApi(token=token)
    repo = f"{user}/{SPACE_NAME}"

    api.create_repo(repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    print("Space:", f"https://huggingface.co/spaces/{repo}")

    if not code_only:
        key = open(os.path.join(ROOT, "secrets", "firebase-admin.json"), encoding="utf-8").read()
        api.add_space_secret(repo, "FIREBASE_SERVICE_ACCOUNT_JSON", key)
        api.add_space_secret(repo, "TICKET_SECRET", pysecrets.token_urlsafe(48))
        api.add_space_secret(repo, "IP_HASH_SALT", pysecrets.token_urlsafe(24))
        api.add_space_variable(repo, "ALLOWED_ORIGINS", ",".join(ORIGINS))
        print("Secrets set: FIREBASE_SERVICE_ACCOUNT_JSON, TICKET_SECRET, IP_HASH_SALT; variable ALLOWED_ORIGINS")

    api.upload_folder(
        repo_id=repo,
        repo_type="space",
        folder_path=os.path.join(ROOT, "api"),
        allow_patterns=["README.md", "Dockerfile", ".dockerignore", "requirements.txt", "app/*.py",
                        "models/pothole.onnx", "models/trash_turhancan.onnx", "models/coco.onnx", "models/models.json"],
        delete_patterns=["app/*.py"],
        commit_message="Deploy RaastaAI API",
    )
    print("Uploaded. Build logs:", f"https://huggingface.co/spaces/{repo}?logs=build")
    print("API URL:", f"https://{user.lower()}-{SPACE_NAME}.hf.space")


if __name__ == "__main__":
    main()
