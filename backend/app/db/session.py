"""Database connections and transaction scope."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
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
