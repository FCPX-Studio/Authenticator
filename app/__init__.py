"""
Application package initialization.

This module exposes the FastAPI app instance so that it can be imported
elsewhere (e.g., when running via `uvicorn app.main:app` or for testing).
"""

from .main import app

__all__ = ["app"]