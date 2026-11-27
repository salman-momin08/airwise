"""Declarative SQLAlchemy 2.x ORM base with deterministic constraint naming conventions."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all AirWise AI SQLAlchemy 2.x ORM models."""
