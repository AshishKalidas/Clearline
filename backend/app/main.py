"""Clearline HTTP application."""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db.session import get_session

app = FastAPI(title="Clearline", version="0.1.0")


@app.get("/healthz")
def healthz(session: Session = Depends(get_session)) -> dict[str, str]:
    """Check process liveness and database connectivity."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "service": "clearline"}
