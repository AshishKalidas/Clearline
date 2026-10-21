"""Shared request authentication and serialization."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.session import get_session

# A successful HTTP response must follow commit, including any commit-time failure.
DB = Annotated[Session, Depends(get_session, scope="function")]


def require_key(x_api_key: str = Header(default="")) -> None:
    """Authenticate every state-changing HTTP endpoint."""
    expected = get_settings().api_key.get_secret_value().encode("utf-8")
    # compare_digest rejects non-ASCII strings; bytes make malformed headers a normal denial.
    if not secrets.compare_digest(x_api_key.encode("utf-8"), expected):
        raise HTTPException(401, "A valid X-API-Key is required")


def reviewer(x_reviewer: str = Header(default="")) -> str:
    """Require a nonempty reviewer identity for human decisions."""
    name = x_reviewer.strip()
    if not name or len(name) > 100:
        raise HTTPException(422, "X-Reviewer is required (1-100 characters)")
    return name
