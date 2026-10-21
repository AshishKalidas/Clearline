"""HTTP success must mean the transaction completed, not just the handler."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.models import AuditEvent, BankLine
from backend.app.db.session import get_session
from backend.app.main import app
from evals.generate_dataset import csv_bytes, generate


def test_commit_failure_returns_error_and_rolls_back_all_import_effects(session: Session) -> None:
    def failing_commit() -> Iterator[Session]:
        try:
            yield session
            # Simulate the database refusing commit after the handler has built its response.
            raise SQLAlchemyError("Synthetic commit failure")
        finally:
            session.rollback()

    app.dependency_overrides[get_session] = failing_commit
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/ingest/bank-lines",
                headers={"X-API-Key": "clearline-local-demo"},
                files={"file": ("bank.csv", csv_bytes(generate()["bank_lines"][:1]))},
            )
        assert response.status_code == 500
        assert session.scalar(select(func.count()).select_from(BankLine)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0
        assert "Synthetic commit failure" not in response.text
    finally:
        app.dependency_overrides.pop(get_session, None)
