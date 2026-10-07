"""Restrict agent tools at the database boundary inside the API transaction."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session


@contextmanager
def agent_scope(session: Session, timeout: float = 5.0) -> Iterator[None]:
    """Use the SELECT/limited-INSERT role, then restore the session identity."""
    postgres = session.get_bind().dialect.name == "postgresql"
    session.flush()
    if postgres:
        session.execute(text("SET LOCAL ROLE clearline_agent"))
        previous_timeout = session.scalar(text("SHOW statement_timeout"))
        session.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": str(max(1, int(min(5.0, timeout) * 1000)))},
        )
    try:
        yield
    finally:
        if postgres:
            session.execute(text("SET LOCAL ROLE NONE"))
            session.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": previous_timeout},
            )
