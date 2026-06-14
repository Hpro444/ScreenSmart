# ScreenSmart chatbot — FastAPI + LangGraph, talks to a local Ollama host.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config.yaml ./
COPY chatbot ./chatbot

EXPOSE 8092

CMD ["uvicorn", "chatbot.main:app", "--host", "0.0.0.0", "--port", "8092"]
