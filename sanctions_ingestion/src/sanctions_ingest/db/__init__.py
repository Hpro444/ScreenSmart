"""Database layer: declarative base, session management, and the generic repository."""

from .base import Base, BaseModel
from .repository import BaseRepository
from .session import get_engine, session_scope, SessionLocal

__all__ = ["Base", "BaseModel", "BaseRepository", "get_engine", "session_scope", "SessionLocal"]
