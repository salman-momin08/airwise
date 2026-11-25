from __future__ import annotations

import os
import sys

# Ensure backend/ is on sys.path when invoked inside Vercel's Python Serverless runtime
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.main import app  # noqa: E402

__all__ = ["app"]
