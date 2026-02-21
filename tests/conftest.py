"""Shared pytest configuration and fixtures for Project 2 tests."""
from __future__ import annotations

import os

# Provide required env vars before any app module is imported
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://doc:doc@localhost:5432/doc")
os.environ.setdefault("EXTRACTION_MODE", "simple")
os.environ.setdefault("OCR_PROVIDER", "mock")
