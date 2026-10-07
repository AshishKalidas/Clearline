"""Validated CSV ingest with stable identities and idempotent conflict handling."""

import csv
import hashlib
import io
import json
from datetime import date
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import BankLine, Customer, Invoice


def stable_id(kind: str, key: str) -> str:
    """Derive a deterministic synthetic UUID."""
    return str(uuid5(NAMESPACE_URL, f"clearline:{kind}:{key}"))


class InvoiceRow(BaseModel):
    """One CSV invoice, including its fictional customer."""

    model_config = ConfigDict(extra="forbid")
    invoice_number: str = Field(pattern=r"^INV-\d{6}$")
    account_code: str = Field(pattern=r"^C-\d{5}$")
    customer_name: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)
    issue_date: date
    due_date: date
    amount_cents: int = Field(gt=0, le=10**12)

    @model_validator(mode="after")
    def valid_dates(self) -> "InvoiceRow":
        if self.due_date < self.issue_date:
            raise ValueError("due date precedes issue date")
        return self


class BankRow(BaseModel):
    """A bank-provided observation. Sequence distinguishes genuine repeated EFTs."""

    model_config = ConfigDict(extra="forbid")
    value_date: date
    amount_cents: int = Field(ge=-(10**12), le=10**12)
    raw_reference: str = Field(max_length=2000)
    payer_name: str = Field(min_length=1, max_length=200)
    payer_account_masked: str = Field(pattern=r"^\d{4}$")
    bank_transaction_id: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def nonzero_amount(self) -> "BankRow":
        if self.amount_cents == 0:
            raise ValueError("zero-value bank lines are not payments")
        return self


def parse_csv(content: bytes) -> list[dict[str, str]]:
    """Decode UTF-8 CSV and reject oversized row sets before changing data."""
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    if not rows or len(rows) > 10000:
        raise ValueError("CSV must contain between 1 and 10000 rows")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV row has an unexpected number of columns")
    return rows


def ingest_invoices(session: Session, content: bytes) -> dict[str, int]:
    """Validate the complete file and insert each invoice at most once."""
    rows = [InvoiceRow.model_validate(row) for row in parse_csv(content)]
    inserted = 0
    for row in rows:
        customer = session.scalar(select(Customer).where(Customer.account_code == row.account_code))
        if customer is None:
            customer = Customer(
                id=stable_id("customer", row.account_code),
                account_code=row.account_code,
                name=row.customer_name,
                notes=row.notes,
            )
            session.add(customer)
            session.flush()
        elif customer.name != row.customer_name:
            raise ValueError("account code is already associated with another customer")
        existing = session.scalar(
            select(Invoice).where(Invoice.invoice_number == row.invoice_number)
        )
        if existing:
            if existing.amount_cents != row.amount_cents or existing.customer_id != customer.id:
                raise ValueError("invoice identity conflicts with existing data")
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
    rows = [BankRow.model_validate(row) for row in parse_csv(content)]
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
