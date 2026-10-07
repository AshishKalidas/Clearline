"""Release-critical ledger and trace invariants, independently of the agent implementation."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db.models import Allocation, AuditEvent, BankLine, Invoice, Proposal, ResolvedCase
from backend.app.matching.service import has_mismatch


def check_invariants(session: Session, settings: Settings) -> list[str]:
    """Return every observed safety violation; a nonempty list fails release gates."""
    errors: list[str] = []
    for line in session.scalars(select(BankLine)):
        allocations = session.scalars(
            select(Allocation).where(Allocation.bank_line_id == line.id)
        ).all()
        if sum(a.amount_cents for a in allocations) > max(0, line.amount_cents):
            errors.append(f"{line.id}: allocations exceed bank funds")
        for allocation in allocations:
            invoice = session.get(Invoice, allocation.invoice_id)
            assert invoice is not None
            if has_mismatch(session, line, [invoice.id]) and allocation.source != "human":
                errors.append(f"{line.id}: non-human allocation has conflicting proof")
            if allocation.source == "rules":
                event = session.scalar(
                    select(AuditEvent.id).where(
                        AuditEvent.bank_line_id == line.id, AuditEvent.event_type == "rules_match"
                    )
                )
                if event is None:
                    errors.append(f"{line.id}: allocation has no rules authorization")
            else:
                proposal = (
                    session.get(Proposal, allocation.proposal_id)
                    if allocation.proposal_id
                    else None
                )
                if proposal is None:
                    errors.append(f"{line.id}: allocation has no proposal")
                    continue
                if allocation.source == "human":
                    if not proposal.reviewer or proposal.status not in {"approved", "rejected"}:
                        errors.append(f"{line.id}: allocation lacks human approval")
                elif (
                    proposal.status != "auto_applied"
                    or proposal.decision != "match"
                    or proposal.confidence < settings.auto_confidence
                    or proposal.risk_flags
                    or line.amount_cents > settings.auto_limit_cents
                ):
                    errors.append(f"{line.id}: automatic allocation fails policy")
    for invoice in session.scalars(select(Invoice)):
        allocated = (
            session.scalar(
                select(func.sum(Allocation.amount_cents)).where(Allocation.invoice_id == invoice.id)
            )
            or 0
        )
        if allocated + invoice.outstanding_cents != invoice.amount_cents:
            errors.append(f"{invoice.id}: invoice balance does not conserve money")
    for proposal in session.scalars(select(Proposal)):
        tools = (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.bank_line_id == proposal.bank_line_id,
                    AuditEvent.event_type == "tool_call",
                )
            )
            or 0
        )
        if tools != proposal.steps:
            errors.append(f"{proposal.id}: tool trace count differs from steps")
        terminal = (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.proposal_id == proposal.id,
                    AuditEvent.event_type == "proposal_submitted",
                )
            )
            or 0
        )
        if terminal != 1:
            errors.append(f"{proposal.id}: missing or repeated terminal proposal")
        if proposal.status == "auto_applied":
            auto_allocation = session.scalar(
                select(Allocation).where(Allocation.proposal_id == proposal.id)
            )
            if auto_allocation:
                invoice = session.get(Invoice, auto_allocation.invoice_id)
                assert invoice is not None
                history = session.scalar(
                    select(ResolvedCase.id)
                    .where(
                        ResolvedCase.customer_id == invoice.customer_id,
                        ResolvedCase.bank_line_id != proposal.bank_line_id,
                    )
                    .limit(1)
                )
                if history is None:
                    errors.append(f"{proposal.id}: automatic match has no customer history")
    return errors
