"""Protocol-level least-privilege and masking checks through the real MCP SDK."""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import BankLine, Base, Customer, Proposal
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from evals.generate_dataset import csv_bytes, generate
from mcp_server.server import read_engine, read_session
from mcp_server.smoke import EXPECTED_TOOLS


def test_mcp_stdio_tools_privacy_and_no_writes(tmp_path: Path) -> None:
    """A client can investigate but cannot mutate or receive raw sensitive patterns."""
    url = f"sqlite:///{tmp_path / 'mcp.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    dataset = generate()
    raw = "fictional@example.invalid"
    with Session(engine) as session:
        ingest_invoices(session, csv_bytes(dataset["invoices"]))
        ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
        customer = session.scalar(
            select(Customer).where(Customer.account_code == dataset["invoices"][0]["account_code"])
        )
        assert customer is not None
        customer.notes = f"Contact {raw} account 88888888 ID 9999999999999"
        customer_id = customer.id
        customer_name = customer.name
        line = session.get(BankLine, dataset["labels"][0]["bank_line_id"])
        assert line is not None
        line_id = line.id
        session.add(
            Proposal(
                bank_line_id=line_id,
                decision="escalate",
                allocations_json=[],
                confidence=0,
                reasoning=f"Investigate {raw}",
                risk_flags=[],
                status="pending",
                policy_reason="Human sign-off",
                model="synthetic-test",
                steps=0,
            )
        )
        session.commit()

    async def check() -> None:
        env = dict(os.environ, DATABASE_URL=url, AGENT_DATABASE_URL="", EMBEDDER="hash")
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "mcp_server.server"], env=env
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == EXPECTED_TOOLS
            assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
            arguments = {
                "search_invoices": {"customer_id": customer_id},
                "get_invoice": {"invoice_number": dataset["invoices"][0]["invoice_number"]},
                "find_customers": {"name_query": customer_name},
                "get_customer": {"customer_id": customer_id},
                "get_payment_history": {"customer_id": customer_id},
                "find_similar_cases": {"bank_line_id": line_id},
                "get_pop_verification": {"bank_line_id": line_id},
                "list_pending_proposals": {},
            }
            for name, args in arguments.items():
                result = await client.call_tool(name, args)
                assert not result.isError, result
                encoded = result.model_dump_json()
                assert all(value not in encoded for value in (raw, "88888888", "9999999999999"))
                if name == "get_customer":
                    assert "[EMAIL_1]" in encoded and "[ACCOUNT_1]" in encoded
                if name == "search_invoices":
                    assert dataset["invoices"][0]["invoice_number"] in encoded
            assert (await client.call_tool("submit_proposal", {})).isError
            assert (await client.call_tool("search_invoices", {"amount_cents": 1.5})).isError
            assert (await client.call_tool("search_invoices", {"tolerance_cents": -1})).isError
            for name, args in (
                ("get_invoice", {"invoice_number": raw}),
                ("find_customers", {"name_query": 9999999999999}),
            ):
                invalid = await client.call_tool(name, args)
                assert invalid.isError
                assert raw not in invalid.model_dump_json()
                assert "9999999999999" not in invalid.model_dump_json()
            missing = await client.call_tool("get_pop_verification", {"bank_line_id": "missing"})
            assert "bank_line_not_found" in missing.model_dump_json()

    asyncio.run(check())
    with Session(engine) as session:
        assert (
            session.scalar(select(Customer.notes).where(Customer.id == customer_id))
            == f"Contact {raw} account 88888888 ID 9999999999999"
        )
        assert session.scalar(text("SELECT count(*) FROM allocations")) == 0
        assert session.scalar(text("SELECT count(*) FROM proposals")) == 1
    engine.dispose()


def test_mcp_database_enforces_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = get_settings().agent_database_url
    if not url or not url.startswith("postgresql"):
        url = f"sqlite:///{tmp_path / 'readonly.db'}"
        engine = create_engine(url)
        Base.metadata.create_all(engine)
        engine.dispose()
        monkeypatch.setenv("AGENT_DATABASE_URL", url)
        get_settings.cache_clear()
    read_engine.cache_clear()
    try:
        with pytest.raises(ValueError, match="Database read failed"), read_session() as session:
            if session.get_bind().dialect.name == "postgresql":
                assert session.scalar(
                    text("SELECT has_table_privilege(current_user, 'audit_events', 'INSERT')")
                )
            session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, created_at, updated_at, actor, event_type, payload_json) "
                    "VALUES ('00000000-0000-0000-0000-000000000001', CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP, 'synthetic-test', 'forbidden', '{}')"
                )
            )
    finally:
        read_engine().dispose()
        read_engine.cache_clear()


def test_stdio_smoke_accepts_an_empty_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean checkout must not need seed data to prove protocol connectivity."""
    from mcp_server.smoke import main

    url = f"sqlite:///{tmp_path / 'empty-mcp.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AGENT_DATABASE_URL", "")
    asyncio.run(main())


def test_stdio_smoke_accepts_empty_postgres_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the clean-checkout condition without touching the seeded demo ledger."""
    from sqlalchemy.engine import make_url

    from evals.run_eval import evaluation_session
    from mcp_server.smoke import main

    agent_url = os.getenv("AGENT_DATABASE_URL", "")
    if not agent_url.startswith("postgresql"):
        pytest.skip("Docker verifies an empty PostgreSQL MCP workspace")
    with evaluation_session() as (session, _):
        schema = session.scalar(text("SELECT current_schema()"))
        isolated_url = make_url(agent_url).update_query_dict(
            {"options": f"-csearch_path={schema},public"}
        )
        monkeypatch.setenv("AGENT_DATABASE_URL", isolated_url.render_as_string(hide_password=False))
        asyncio.run(main())
