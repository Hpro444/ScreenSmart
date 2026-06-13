# ScreenSmart API image — serves screensmart.api:app (FastAPI/uvicorn).
# The trained model is baked in; the sanctions data is provided at runtime via a
# volume (see docker-compose.yml at the repo root), so the image stays small and the
# data isn't duplicated into every build.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# dependencies first (cached layer)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# application code + trained model artifact
COPY src ./src
COPY models ./models

# project-root marker: config.py walks up to this to locate /app as the root, so the
# data volume mounted at /app/data and the baked /app/models both resolve correctly.
RUN touch /app/.screensmart-root

EXPOSE 8000

# host=0.0.0.0 so the port is reachable outside the container (compose maps it to the host)
CMD ["uvicorn", "screensmart.api:app", "--host", "0.0.0.0", "--port", "8000"]
