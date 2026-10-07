"""Load the offline demonstration idempotently, without putting labels in the database."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.audit.service import record_event
from backend.app.db.models import Allocation, BankLine, Customer, Invoice, ResolvedCase
from backend.app.db.session import SessionLocal
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices, stable_id
from backend.app.retrieval.index import index_case, index_customer, index_runbook


def load_dataset(session: Session, directory: Path) -> dict[str, Any]:
    """Import observations, independent pre-resolved history and the fictional runbook."""
    invoices = ingest_invoices(session, (directory / "invoices.csv").read_bytes())
    bank = ingest_bank_lines(session, (directory / "bank_lines.csv").read_bytes())
    history = json.loads((directory / "history.json").read_text())
    for n, item in enumerate(history):
        if session.get(ResolvedCase, item["id"]):
            continue
        customer = session.get(Customer, item["customer_id"])
        assert customer is not None
        number = f"INV-{900000 + n:06d}"
        amount = 20000 + (n % 10) * 1000
        day = date(2026, 7, 1) + timedelta(days=n % 20)
        invoice = Invoice(
            id=stable_id("invoice", number),
            invoice_number=number,
            customer_id=customer.id,
            issue_date=day - timedelta(days=10),
            due_date=day,
            amount_cents=amount,
            outstanding_cents=0,
            status="paid",
        )
        line = BankLine(
            id=stable_id("history-bank", item["id"]),
            value_date=day,
            amount_cents=amount,
            raw_reference=number,
            payer_name=customer.name,
            payer_account_masked="0042",
            line_hash=item["id"],
            status="matched",
        )
        session.add_all([invoice, line])
        session.flush()
        session.add(
            Allocation(
                bank_line_id=line.id, invoice_id=invoice.id, amount_cents=amount, source="rules"
            )
        )
        resolution = {
            "decision": "match",
            "allocations": [{"invoice_number": number, "amount_cents": amount}],
            "historical": True,
        }
        case = ResolvedCase(
            id=item["id"],
            bank_line_id=line.id,
            customer_id=customer.id,
            summary_text=item["summary_text"],
            resolution_json=resolution,
            resolved_by="rules",
        )
        index_case(case)
        session.add(case)
        record_event(
            session,
            "rules_match",
            {"invoice_number": number, "amount_cents": amount, "historical": True},
            bank_line_id=line.id,
        )
    for customer in session.scalars(select(Customer)):
        index_customer(customer)
    chunks = index_runbook(session, Path("docs/runbook.md").read_text())
    session.flush()
    if session.get_bind().dialect.name == "postgresql":
        for table in ("resolved_cases", "customers", "runbook_chunks"):
            session.execute(text(f"REINDEX INDEX {table}_cosine"))
            session.execute(text(f"ANALYZE {table}"))
    return {
        "invoices": invoices,
        "bank_lines": bank,
        "history_cases": len(history),
        "runbook_chunks": chunks,
    }


def main() -> None:
    """Seed the database configured by DATABASE_URL."""
    with SessionLocal.begin() as session:
        print(json.dumps(load_dataset(session, Path("evals/datasets/seed-42")), indent=2))


if __name__ == "__main__":
    main()
