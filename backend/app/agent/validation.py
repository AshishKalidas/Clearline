"""Server-side proposal validation and allocation invariants."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agent.schemas import ProposalInput
from backend.app.db.models import BankLine, Invoice
from backend.app.matching.rules import has_injection


def validate_proposal(
    session: Session,
    line: BankLine,
    proposal: ProposalInput,
    *,
    human: bool = False,
) -> list[Invoice]:
    """Reject inconsistent, overdrawn, nonexistent or instruction-induced allocations."""
    allocations = proposal.allocations
    if proposal.decision in {"duplicate", "escalate"}:
        if allocations:
            raise ValueError("non-allocation decision includes allocations")
        return []
    if not human and has_injection(line.raw_reference):
        raise ValueError("untrusted instruction text must escalate")
    if not allocations or line.amount_cents <= 0:
        raise ValueError("a positive payment and allocations are required")
    numbers = [a.invoice_number for a in allocations]
    if len(set(numbers)) != len(numbers):
        raise ValueError("duplicate invoice in allocation set")
    invoices: list[Invoice] = []
    for allocation in allocations:
        invoice = session.scalar(
            select(Invoice)
            .where(Invoice.invoice_number == allocation.invoice_number)
            .with_for_update()
        )
        if invoice is None:
            raise ValueError("invoice does not exist")
        # Excess EFT money remains unapplied; even overpayment cannot overdraw an invoice.
        if allocation.amount_cents > invoice.outstanding_cents:
            raise ValueError("allocation exceeds current invoice balance")
        invoices.append(invoice)
    total = sum(a.amount_cents for a in allocations)
    if total > line.amount_cents:
        raise ValueError("allocations exceed received funds")
    if proposal.decision == "match" and (
        len(invoices) != 1 or total != line.amount_cents or total != invoices[0].outstanding_cents
    ):
        raise ValueError("match must settle one full invoice with the full payment")
    if proposal.decision == "partial" and (
        len(invoices) != 1 or total != line.amount_cents or total >= invoices[0].outstanding_cents
    ):
        raise ValueError("partial must allocate one payment below the invoice balance")
    if proposal.decision == "split" and (len(invoices) < 2 or total != line.amount_cents):
        raise ValueError("split needs multiple invoices and the full payment")
    if proposal.decision == "overpayment" and (
        len(invoices) != 1 or total >= line.amount_cents or total != invoices[0].outstanding_cents
    ):
        raise ValueError("overpayment must settle one invoice and retain the excess")
    return invoices
