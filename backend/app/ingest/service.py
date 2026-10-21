"""Validated CSV ingest with stable identities and idempotent conflict handling."""

import hashlib
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import BankLine, Customer, Invoice
from backend.app.ingest.validation import (
    BankRow,
    CsvInputError,
    CsvIssue,
    InvoiceRow,
    validate_rows,
)
from backend.app.ingest.validation import parse_csv as parse_csv
from backend.app.retrieval.index import index_customer


def stable_id(kind: str, key: str) -> str:
    """Derive a deterministic synthetic UUID."""
    return str(uuid5(NAMESPACE_URL, f"clearline:{kind}:{key}"))


def ingest_invoices(session: Session, content: bytes) -> dict[str, int]:
    """Validate the complete file and insert each invoice at most once."""
    rows = validate_rows(InvoiceRow, content)
    inserted = 0
    for position, row in enumerate(rows, start=2):
        customer = session.scalar(select(Customer).where(Customer.account_code == row.account_code))
        if customer is None:
            customer = Customer(
                id=stable_id("customer", row.account_code),
                account_code=row.account_code,
                name=row.customer_name,
                notes=row.notes,
            )
            index_customer(customer)
            session.add(customer)
            session.flush()
        elif customer.name != row.customer_name:
            raise CsvInputError(
                [
                    CsvIssue(
                        row=position,
                        field="account_code",
                        message="Customer account conflicts with existing workspace data.",
                    )
                ]
            )
        existing = session.scalar(
            select(Invoice).where(Invoice.invoice_number == row.invoice_number)
        )
        if existing:
            if (
                existing.amount_cents != row.amount_cents
                or existing.customer_id != customer.id
                or existing.issue_date != row.issue_date
                or existing.due_date != row.due_date
            ):
                raise CsvInputError(
                    [
                        CsvIssue(
                            row=position,
                            field="invoice_number",
                            message="Invoice conflicts with existing workspace data.",
                        )
                    ]
                )
            continue
        session.add(
            Invoice(
                id=stable_id("invoice", row.invoice_number),
                invoice_number=row.invoice_number,
                customer_id=customer.id,
                issue_date=row.issue_date,
                due_date=row.due_date,
                amount_cents=row.amount_cents,
                outstanding_cents=row.amount_cents,
            )
        )
        session.flush()
        inserted += 1
    return {"inserted": inserted, "skipped": len(rows) - inserted}


def bank_hash(row: BankRow) -> str:
    """Hash the canonical bank transaction, preserving real repeated-payment identity."""
    canonical = json.dumps(row.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def ingest_bank_lines(session: Session, content: bytes) -> dict[str, int]:
    """Import bank transactions idempotently on a unique content hash."""
    rows = validate_rows(BankRow, content)
    inserted = 0
    for row in rows:
        digest = bank_hash(row)
        if session.scalar(select(BankLine.id).where(BankLine.line_hash == digest)):
            continue
        values: dict[str, Any] = row.model_dump(exclude={"bank_transaction_id"})
        session.add(BankLine(id=stable_id("bank", digest), line_hash=digest, **values))
        session.flush()
        inserted += 1
    return {"inserted": inserted, "skipped": len(rows) - inserted}
