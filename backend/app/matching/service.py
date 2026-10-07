"""Transactional orchestration around the pure exact and reversal rules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.audit.service import record_event
from backend.app.db.models import Allocation, BankLine, Invoice, PopDocument, ResolvedCase
from backend.app.matching.rules import (
    InvoiceCandidate,
    LineSnapshot,
    exact_match,
    reversal_match,
)
from backend.app.retrieval.index import index_case


def snapshot(line: BankLine) -> LineSnapshot:
    """Project persistence data into a pure rule input."""
    return LineSnapshot(
        line.id, line.value_date, line.amount_cents, line.payer_name, line.raw_reference
    )


def has_mismatch(session: Session, line: BankLine, invoice_ids: list[str]) -> bool:
    """Block automatic writes when any related claim disagrees with the bank feed."""
    return (
        session.scalar(
            select(PopDocument.id)
            .where(
                PopDocument.verdict == "mismatch",
                (PopDocument.matched_bank_line_id == line.id)
                | PopDocument.claimed_invoice_id.in_(invoice_ids),
            )
            .limit(1)
        )
        is not None
    )


def run_rules(session: Session) -> dict[str, int]:
    """Apply exact matches and uniquely evidenced reversals atomically."""
    counts = {"matched": 0, "reversed": 0}
    lines = session.scalars(
        select(BankLine)
        .where(BankLine.status == "unmatched")
        .order_by(BankLine.value_date, BankLine.id)
        .with_for_update()
    ).all()
    for line in lines:
        if line.amount_cents < 0:
            prior = session.scalars(select(BankLine).where(BankLine.status == "matched")).all()
            original_id = reversal_match(snapshot(line), [snapshot(p) for p in prior])
            if original_id:
                original = session.get(BankLine, original_id)
                assert original is not None
                unwind(session, line, original)
                counts["reversed"] += 1
            continue
        invoices = session.scalars(select(Invoice).where(Invoice.outstanding_cents > 0)).all()
        number = exact_match(
            line.raw_reference,
            line.amount_cents,
            [InvoiceCandidate(i.invoice_number, i.outstanding_cents) for i in invoices],
        )
        if number is None:
            continue
        invoice = next(i for i in invoices if i.invoice_number == number)
        if has_mismatch(session, line, [invoice.id]):
            continue
        session.add(
            Allocation(
                bank_line_id=line.id,
                invoice_id=invoice.id,
                amount_cents=line.amount_cents,
                source="rules",
            )
        )
        invoice.outstanding_cents = 0
        invoice.status = "paid"
        line.status = "matched"
        case = ResolvedCase(
            bank_line_id=line.id,
            customer_id=invoice.customer_id,
            summary_text=(f"Exact full payment by {line.payer_name} for {invoice.invoice_number}."),
            resolution_json={
                "decision": "match",
                "allocations": [
                    {
                        "invoice_number": invoice.invoice_number,
                        "amount_cents": line.amount_cents,
                    }
                ],
            },
            resolved_by="rules",
        )
        index_case(case)
        session.add(case)
        record_event(
            session,
            "rules_match",
            {"invoice_number": number, "amount_cents": line.amount_cents},
            bank_line_id=line.id,
        )
        counts["matched"] += 1
    return counts


def unwind(session: Session, reversal: BankLine, original: BankLine) -> None:
    """Undo applied money, preserving the allocation values in append-only audit evidence."""
    allocations = session.scalars(
        select(Allocation).where(Allocation.bank_line_id == original.id)
    ).all()
    undone: list[dict[str, str | int]] = []
    for allocation in allocations:
        invoice = session.get(Invoice, allocation.invoice_id, with_for_update=True)
        assert invoice is not None
        invoice.outstanding_cents += allocation.amount_cents
        invoice.status = (
            "open" if invoice.outstanding_cents == invoice.amount_cents else "partially_paid"
        )
        undone.append(
            {"invoice_number": invoice.invoice_number, "amount_cents": allocation.amount_cents}
        )
        session.delete(allocation)
    original.status = reversal.status = "reversed"
    record_event(
        session,
        "reversal",
        {"original_bank_line_id": original.id, "undone_allocations": undone},
        bank_line_id=reversal.id,
    )
    record_event(
        session, "reversed_by", {"reversal_bank_line_id": reversal.id}, bank_line_id=original.id
    )
