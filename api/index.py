"""Vercel Python serverless entrypoint exposing the FastAPI ASGI application."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ is on sys.path when invoked inside Vercel's Python Serverless runtime
BACKEND_ROOT = str(Path(__file__).resolve().parents[1] / "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.main import app  # noqa: E402

__all__ = ["app"]
