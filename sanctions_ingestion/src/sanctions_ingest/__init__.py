"""ScreenSmart sanctions-ingestion service.

Downloads every public sanctions source (the same set as
``screensmart_app/src/download_data.py``) on a daily schedule and loads it into
Postgres behind SQLAlchemy ORM models and Pydantic schemas. Standalone — it does
not import or modify ``screensmart_app``.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
