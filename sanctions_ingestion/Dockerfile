# Sanctions-ingestion service: runs the blocking daily scheduler.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "sqlalchemy>=2.0,<2.1" "psycopg[binary]>=3.2,<3.3" \
        "pydantic>=2.13" "pydantic-settings>=2.14" "python-dotenv>=1.0" \
        "requests>=2.32" "lxml>=5" "apscheduler>=3.10,<4"

COPY src ./src

# config.py walks up to the `.screensmart-root` marker; create one at /app so the
# repo-root discovery resolves inside the container (data/ is mounted at /app/data).
RUN touch /app/.screensmart-root

CMD ["python", "-m", "sanctions_ingest.cli", "run-scheduler"]
