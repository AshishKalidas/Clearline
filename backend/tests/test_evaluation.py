import asyncio
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.agent.invariants import check_invariants
from backend.app.config import Settings
from backend.app.db.models import Allocation, BankLine, Invoice
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from evals.gates import release_gates
from evals.generate_dataset import csv_bytes, generate
from evals.run_eval import evaluate, evaluation_session, refresh_lift
from evals.update_results import results_table, update_readme


def test_release_gate_detects_a_deliberately_broken_metric() -> None:
    metrics = {
        "rules_precision": 1,
        "false_allocation_rate": 0,
        "escalation_recall": 1,
        "injection_resistance": 1,
        "pop_verdict_accuracy": 1,
        "forged_pop_recall": 1,
        "incomplete_investigations": 0,
    }
    assert all(release_gates(metrics, "stub", []).values())
    # This is the deliberate gate break required by M7; restore valid metrics afterwards.
    metrics["false_allocation_rate"] = 0.1
    assert not all(release_gates(metrics, "stub", []).values())
    metrics["false_allocation_rate"] = 0
    assert all(release_gates(metrics, "stub", []).values())
    assert not all(release_gates(metrics, "stub", ["unauthorized allocation"]).values())
    assert not all(release_gates({}, "claude", []).values())


def test_invariant_catches_unauthorized_ledger_write(session: Session) -> None:
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    line = session.get(BankLine, dataset["labels"][0]["bank_line_id"])
    assert line is not None
    invoice = (
        session.query(Invoice).filter_by(invoice_number=dataset["labels"][0]["invoices"][0]).one()
    )
    session.add(
        Allocation(
            bank_line_id=line.id,
            invoice_id=invoice.id,
            amount_cents=line.amount_cents,
            source="agent_auto",
        )
    )
    session.flush()
    assert any("no proposal" in error for error in check_invariants(session, Settings()))


def test_real_eval_reports_and_readme_table(tmp_path: Path, monkeypatch) -> None:
    # Unit suite stays hermetic; the make eval command independently exercises PostgreSQL.
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    report = asyncio.run(evaluate("stub", True, tmp_path / "reports"))
    assert report["passed"], report["gates"]
    assert report["counts"]["bank_cases"] == 400
    assert report["counts"]["auto_applied"] > 0
    assert report["counts"]["wrong_auto_applied"] == 0
    report = asyncio.run(evaluate("stub", False, tmp_path / "reports"))
    assert report["passed"]
    assert report["metrics"]["retrieval_lift"] == 0
    for switch in ("on", "off"):
        folder = tmp_path / "reports" / f"stub-{switch}"
        assert json.loads((folder / "report.json").read_text())["passed"]
        assert (folder / "report.md").exists()
        assert (folder / "failures.jsonl").read_text() == ""
    table = results_table(tmp_path / "reports")
    assert "Scripted baseline" in table and "100.00%" in table
    assert "No full live-provider evaluation is published." in table
    assert "Claude" not in table and "MiMo" not in table
    assert f"0 / {report['counts']['auto_applied']}" in table
    readme = tmp_path / "README.md"
    readme.write_text("Intro\n<!-- RESULTS:START -->\nold\n<!-- RESULTS:END -->\nFooter")
    update_readme(readme, tmp_path / "reports")
    assert table in readme.read_text()
    assert readme.read_text().endswith("Footer")


@pytest.mark.parametrize(
    "mismatch", ["evaluation_id", "agent_protocol_sha256", "live_configuration"]
)
def test_retrieval_lift_rejects_different_execution_protocols_or_routes(
    tmp_path: Path, mismatch: str
) -> None:
    source = json.loads(Path("evals/reports/stub-on/report.json").read_text())
    source.update(
        evaluation_id="same-execution",
        agent_protocol_sha256="a" * 64,
        live_configuration={"upstream_provider": "same-provider"},
    )
    for mode in ("on", "off"):
        folder = tmp_path / f"stub-{mode}"
        folder.mkdir()
        report = dict(source)
        if mode == "off":
            report[mismatch] = "different" if mismatch != "live_configuration" else {}
        (folder / "report.json").write_text(json.dumps(report))
    refresh_lift("stub", tmp_path)
    for mode in ("on", "off"):
        report = json.loads((tmp_path / f"stub-{mode}/report.json").read_text())
        assert report["metrics"]["retrieval_lift"] is None


def test_readme_keeps_failed_live_results_visible_and_omits_pilots(tmp_path: Path) -> None:
    source = json.loads(Path("evals/reports/stub-on/report.json").read_text())
    baseline = tmp_path / "stub-on"
    baseline.mkdir()
    (baseline / "report.json").write_text(json.dumps(source))
    live = tmp_path / "mimo-on"
    live.mkdir()
    source.update(
        provider="mimo",
        baseline=False,
        model="offline-formatting-fixture",
        passed=False,
        evaluation_scope="full",
    )
    source["metrics"].update(model_api_cost_usd=0.012345, incomplete_investigations=2)
    source["gates"] = release_gates(source["metrics"], "mimo", [])
    (live / "report.json").write_text(json.dumps(source))
    table = results_table(tmp_path)
    assert "offline-formatting-fixture" in table
    assert "$0.012345 | Failed" in table
    source["evaluation_scope"] = "pilot"
    (live / "report.json").write_text(json.dumps(source))
    assert "offline-formatting-fixture" not in results_table(tmp_path)


def test_postgres_evaluation_schema_is_isolated() -> None:
    url = os.getenv("MIGRATION_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Docker verifies PostgreSQL evaluation isolation")
    admin = create_engine(url)
    with admin.connect() as connection:
        before = connection.scalar(text("SELECT count(*) FROM public.customers"))
    with evaluation_session() as (session, database):
        assert database == "postgresql16-pgvector"
        schema = session.scalar(text("SELECT current_schema()"))
        assert schema and schema.startswith("eval_")
        assert (
            session.scalar(
                text(
                    "SELECT table_schema FROM information_schema.tables "
                    "WHERE table_name = 'customers' AND table_schema = current_schema()"
                )
            )
            == schema
        )
        assert session.scalar(text("SELECT count(*) FROM customers")) == 0
    with admin.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM public.customers")) == before
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_namespace WHERE nspname = :schema"),
                {"schema": schema},
            )
            == 0
        )
    admin.dispose()
