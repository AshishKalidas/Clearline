import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.app.agent.llm.base import ModelReply
from backend.app.agent.llm.stub import StubLLM
from backend.app.agent.loop import investigate
from backend.app.audit.service import record_event
from backend.app.config import Settings, get_settings
from backend.app.db.models import AuditEvent, BankLine, Customer
from backend.app.db.permissions import agent_scope
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from backend.app.privacy.masking import Masker
from backend.app.privacy.retention import purge
from evals.generate_dataset import csv_bytes, generate

RAW = ["9999999999999", "88888888", "+27 00 000 0000", "fictional@example.invalid"]


def test_stable_mask_and_local_restore() -> None:
    masker = Masker()
    original = {
        "text": " ".join(RAW) + " INV-100003",
        "amount_cents": 123456789,
        "id": "12345678-1234-1234-1234-123456789abc",
    }
    clean = masker.clean(original)
    assert all(raw not in json.dumps(clean) for raw in RAW)
    assert "INV-100003" in clean["text"]
    assert clean["amount_cents"] == original["amount_cents"]
    assert clean["id"] == original["id"]
    assert clean == masker.clean(original)
    assert masker.restore(clean) == original


class CapturingStub(StubLLM):
    def __init__(self) -> None:
        self.requests: list[list[dict[str, Any]]] = []

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        self.requests.append(messages)
        encoded = json.dumps(messages)
        assert all(raw not in encoded for raw in RAW)
        return await super().complete(messages, schemas, timeout)


def test_every_outbound_request_and_audit_masked(session: Session) -> None:
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    line = session.get(BankLine, dataset["labels"][160]["bank_line_id"])
    assert line is not None
    customer = session.scalar(select(Customer).where(Customer.name == line.payer_name))
    assert customer is not None
    line.payer_name += " " + RAW[3]
    customer.name = line.payer_name
    line.raw_reference += " " + " ".join(RAW[:3])
    client = CapturingStub()
    asyncio.run(investigate(session, line, client, Settings()))
    assert len(client.requests) == 6
    for event in session.scalars(select(AuditEvent)):
        assert all(raw not in json.dumps(event.payload_json) for raw in RAW)
    event = record_event(session, "test", {"text": " ".join(RAW)}, actor=RAW[3])
    assert RAW[3] not in event.actor


def test_retention(tmp_path: Path) -> None:
    expired = tmp_path / "old.pdf"
    fresh = tmp_path / "fresh.pdf"
    excluded = tmp_path / "not-a-proof.txt"
    for path in (expired, fresh, excluded):
        path.write_bytes(b"synthetic")
    now = 1800000000
    old = now - 60 * 86400
    os.utime(expired, (old, old))
    os.utime(fresh, (now, now))
    os.utime(excluded, (old, old))
    (tmp_path / "symlink.pdf").symlink_to(fresh)
    assert purge(tmp_path, 30, now=now + 1) == 1
    assert fresh.exists() and excluded.exists()


def test_postgres_permissions() -> None:
    url = get_settings().database_url
    if not url.startswith("postgresql"):
        pytest.skip("PostgreSQL integration runs through make test in Docker")
    engine = create_engine(url)
    with Session(engine) as session:
        with agent_scope(session):
            assert session.scalar(text("SELECT current_user")) == "clearline_agent"
            assert session.scalar(
                text("SELECT has_table_privilege(current_user, 'invoices', 'SELECT')")
            )
            assert not session.scalar(
                text("SELECT has_table_privilege(current_user, 'allocations', 'INSERT')")
            )
            assert not session.scalar(
                text("SELECT has_table_privilege(current_user, 'invoices', 'UPDATE')")
            )
        assert session.scalar(text("SELECT current_user")) != "clearline_agent"
        with pytest.raises(DBAPIError), session.begin_nested():
            session.execute(text("DELETE FROM audit_events"))
    engine.dispose()
