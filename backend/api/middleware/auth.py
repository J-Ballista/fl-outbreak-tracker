"""
API key authentication dependency.

Reads API_KEY from environment (set in .env).
Apply with `dependencies=[Depends(require_api_key)]` on routers or routes.
Health/root routes are excluded at the app level.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

_header_scheme = APIKeyHeader(name="Authorization", auto_error=False)

_API_KEY: str | None = None


def _get_configured_key() -> str | None:
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = os.getenv("API_KEY")
    return _API_KEY


async def require_api_key(authorization: str | None = Security(_header_scheme)) -> None:
    """
    FastAPI dependency that enforces Bearer token auth.

    If API_KEY env var is not set, auth is disabled (dev mode).
    """
    key = _get_configured_key()
    if key is None:
        # No key configured — allow all (local dev)
        return

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
