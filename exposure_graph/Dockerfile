# Exposure-graph Kafka worker (crypto graph-hop tracing).
# Runs python -m screensmart.worker — its own container (package name `screensmart`
# collides with screensmart_app, so they must never share a process).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt aiokafka==0.12.0
COPY src ./src

CMD ["python", "-m", "screensmart.worker"]
