"""Database connections and transaction scope."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings

Path("data").mkdir(exist_ok=True)
engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Commit successful requests and roll back failed requests."""
    with SessionLocal() as session:
        with session.begin():
            yield session


def lock_workflow(session: Session) -> None:
    """Serialize bank, proof and ledger mutations across API processes."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(724193)"))
