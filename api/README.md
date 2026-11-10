---
title: RaastaAI API
emoji: 🛣️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: agpl-3.0
short_description: Pothole & garbage photo checks for the RaastaAI pilot
---

# RaastaAI API (pilot concept)

Backend for RaastaAI, a hackathon **pilot concept** for reporting potholes and garbage from a
photo. It is **not connected to any government authority**.

- `POST /classify`: the AI *suggests* pothole / garbage / uncertain / not an issue. It never creates a report.
- `POST /reports`: the citizen confirms the category and the pin. Photo metadata (EXIF/GPS) is stripped before storage.
  Duplicates within 25 m and 7 days are merged; 3+ reports within 50 m in 30 days form a hotspot.
- `GET /reports/{id}`: public status (no location, no photo).
- `POST /admin/reports/{id}/status`, `GET /admin/reports/{id}/image`: admin only (Firebase custom claim, checked on the server).

Models (pretrained, no training; exported to ONNX, run with onnxruntime on CPU):
- Pothole: YOLOv8n-seg from [FarzadNekouee/YOLOv8_Pothole_Segmentation_Road_Damage_Assessment](https://github.com/FarzadNekouee/YOLOv8_Pothole_Segmentation_Road_Damage_Assessment)
- Garbage: YOLOv8m-seg trash model by turhancan97
- Relevance gate (people / animals): Ultralytics YOLOv8n COCO

Ultralytics YOLOv8 weights are AGPL-3.0, so this service and its source are published under **AGPL-3.0**.

Secrets (Space settings): `FIREBASE_SERVICE_ACCOUNT_JSON`, `TICKET_SECRET`, `IP_HASH_SALT`, `ALLOWED_ORIGINS`.
