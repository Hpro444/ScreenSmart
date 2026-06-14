# One image for all three streaming services; the compose `command:` selects which to run
# (pipeline.ingest:app / pipeline.ws_gateway:app / pipeline.accumulator).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY pipeline ./pipeline

EXPOSE 8090 8091
# default; overridden per service in docker-compose.yml
CMD ["python", "-m", "pipeline.accumulator"]
