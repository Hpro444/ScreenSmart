"""Run the ScreenSmart API.

    .venv\\Scripts\\python.exe src\\serve.py
    -> http://127.0.0.1:8000/docs  (interactive Swagger UI)
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # make `screensmart` importable
import uvicorn

if __name__ == "__main__":
    uvicorn.run("screensmart.api:app", host="127.0.0.1", port=8000, log_level="info")
