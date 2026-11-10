# RaastaAI API: Hugging Face Space (Docker SDK, free CPU basic tier).
# Secrets to set on the Space: FIREBASE_SERVICE_ACCOUNT_JSON, TICKET_SECRET, IP_HASH_SALT, ALLOWED_ORIGINS
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MODEL_DIR=/home/user/app/models MODEL_THREADS=2 PORT=7860

RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces run the container as uid 1000
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user app ./app
COPY --chown=user models/*.onnx models/models.json ./models/

EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7860/health')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
