"""Typed persistence model. Monetary values are always integer cents."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Common UUID identity and timestamps."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


vector_type = Vector(384).with_variant(JSON(), "sqlite")


class Customer(Base):
    """A fictional customer and locally embedded payment notes."""

    __tablename__ = "customers"
    name: Mapped[str]
    account_code: Mapped[str] = mapped_column(unique=True)
    notes: Mapped[str] = mapped_column(default="")
    notes_embedding: Mapped[list[float] | None] = mapped_column(vector_type)


class Invoice(Base):
    """An invoice's original value and current collectible balance."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("amount_cents > 0"),
        CheckConstraint("outstanding_cents >= 0 AND outstanding_cents <= amount_cents"),
        CheckConstraint("status IN ('open', 'partially_paid', 'paid')"),
    )
    invoice_number: Mapped[str] = mapped_column(unique=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    issue_date: Mapped[date]
    due_date: Mapped[date]
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    outstanding_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(default="open")


class BankLine(Base):
    """An immutable imported bank observation, with workflow status."""

    __tablename__ = "bank_lines"
    __table_args__ = (
        CheckConstraint("amount_cents != 0"),
        CheckConstraint("status IN ('unmatched', 'matched', 'in_review', 'escalated', 'reversed')"),
    )
    value_date: Mapped[date]
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    raw_reference: Mapped[str]
    payer_name: Mapped[str]
    payer_account_masked: Mapped[str] = mapped_column(default="0000")
    line_hash: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(default="unmatched", index=True)


class Proposal(Base):
    """An agent recommendation and independent policy/human decision."""

    __tablename__ = "proposals"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
        CheckConstraint(
            "decision IN ('match','partial','split','overpayment','duplicate','escalate')"
        ),
        CheckConstraint("status IN ('pending','auto_applied','approved','rejected')"),
    )
    bank_line_id: Mapped[str] = mapped_column(ForeignKey("bank_lines.id"), unique=True)
    decision: Mapped[str]
    allocations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    confidence: Mapped[float]
    reasoning: Mapped[str]
    evidence_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="pending", index=True)
    policy_reason: Mapped[str] = mapped_column(default="")
    reviewer: Mapped[str | None]
    review_note: Mapped[str | None]
    model: Mapped[str] = mapped_column(default="stub")
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    steps: Mapped[int] = mapped_column(default=0)


class Allocation(Base):
    """Money applied only by rules, a policy-authorized proposal, or a reviewer."""

    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("amount_cents > 0"),
        CheckConstraint("source IN ('rules','agent_auto','human')"),
    )
    bank_line_id: Mapped[str] = mapped_column(ForeignKey("bank_lines.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str]
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"))


class ResolvedCase(Base):
    """Masked, retrievable resolution indexed in the resolving transaction."""

    __tablename__ = "resolved_cases"
    bank_line_id: Mapped[str] = mapped_column(ForeignKey("bank_lines.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    summary_text: Mapped[str]
    resolution_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    resolved_by: Mapped[str]
    embedding: Mapped[list[float] | None] = mapped_column(vector_type)


class RunbookChunk(Base):
    """A locally embedded policy section."""

    __tablename__ = "runbook_chunks"
    section: Mapped[str] = mapped_column(unique=True)
    text: Mapped[str]
    embedding: Mapped[list[float] | None] = mapped_column(vector_type)


class PopDocument(Base):
    """Extracted claim and each bank-feed verification check."""

    __tablename__ = "pop_documents"
    __table_args__ = (
        CheckConstraint("verdict IN ('verified','not_received','mismatch','unreadable')"),
    )
    filename: Mapped[str]
    claimed_invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"))
    extracted_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    verdict: Mapped[str]
    matched_bank_line_id: Mapped[str | None] = mapped_column(ForeignKey("bank_lines.id"))
    checks_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class AuditEvent(Base):
    """Append-only evidence. No application update or delete path exists."""

    __tablename__ = "audit_events"
    bank_line_id: Mapped[str | None] = mapped_column(ForeignKey("bank_lines.id"), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), index=True)
    actor: Mapped[str]
    event_type: Mapped[str]
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
