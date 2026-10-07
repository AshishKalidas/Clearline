"""The policy and human pathways are the only non-rule ledger writers."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agent.policy import PolicyFacts, evaluate_policy
from backend.app.agent.schemas import ProposalInput
from backend.app.agent.validation import validate_proposal
from backend.app.audit.service import record_event
from backend.app.config import Settings, get_settings
from backend.app.db.models import Allocation, BankLine, Proposal, ResolvedCase
from backend.app.matching.service import has_mismatch


def proposal_input(proposal: Proposal) -> ProposalInput:
    """Recover the original typed recommendation for independent revalidation."""
    return ProposalInput.model_validate(
        {
            "decision": proposal.decision,
            "allocations": proposal.allocations_json,
            "confidence": proposal.confidence,
            "reasoning": proposal.reasoning,
            "evidence": proposal.evidence_json,
            "risk_flags": proposal.risk_flags,
        }
    )


def policy_for(
    session: Session,
    line: BankLine,
    value: ProposalInput,
    settings: Settings,
) -> tuple[bool, str]:
    """Compute safety facts from current database state, not model claims."""
    invoices = validate_proposal(session, line, value)
    history = (
        bool(invoices)
        and session.scalar(
            select(ResolvedCase.id)
            .where(
                ResolvedCase.customer_id == invoices[0].customer_id,
                ResolvedCase.bank_line_id != line.id,
            )
            .limit(1)
        )
        is not None
    )
    return evaluate_policy(
        PolicyFacts(
            value.decision,
            value.confidence,
            line.amount_cents,
            value.risk_flags,
            has_mismatch(session, line, [i.id for i in invoices]),
            history,
        ),
        settings,
    )


def apply_resolution(
    session: Session,
    line: BankLine,
    proposal: Proposal,
    value: ProposalInput,
    source: str,
    reviewer: str | None = None,
    settings: Settings | None = None,
) -> ResolvedCase:
    """Lock, revalidate and apply money; resolve and audit in the same transaction."""
    if line.status not in {"unmatched", "in_review", "escalated"}:
        raise ValueError("bank line has already been resolved")
    if session.scalar(select(Allocation.id).where(Allocation.bank_line_id == line.id)):
        raise ValueError("bank line already has allocations")
    invoices = validate_proposal(session, line, value, human=source == "human")
    if source == "human" and not reviewer:
        raise ValueError("a reviewer identity is required")
    if source == "agent_auto" and proposal.status != "auto_applied":
        raise ValueError("automatic resolution requires policy authorization")
    if (
        source == "agent_auto"
        and not policy_for(session, line, value, settings or get_settings())[0]
    ):
        raise ValueError("automatic resolution fails current policy")
    for allocation, invoice in zip(value.allocations, invoices, strict=True):
        session.add(
            Allocation(
                bank_line_id=line.id,
                invoice_id=invoice.id,
                amount_cents=allocation.amount_cents,
                source=source,
                proposal_id=proposal.id,
            )
        )
        invoice.outstanding_cents -= allocation.amount_cents
        invoice.status = "paid" if invoice.outstanding_cents == 0 else "partially_paid"
    line.status = "escalated" if value.decision in {"escalate", "duplicate"} else "matched"
    resolution = value.model_dump(mode="json")
    resolution["unapplied_cents"] = max(
        0, line.amount_cents - sum(a.amount_cents for a in value.allocations)
    )
    case = ResolvedCase(
        bank_line_id=line.id,
        customer_id=invoices[0].customer_id if invoices else None,
        summary_text=f"Payer {line.payer_name}; reference {line.raw_reference}; "
        f"amount_cents {line.amount_cents}; {value.decision}: {value.reasoning}",
        resolution_json=resolution,
        resolved_by=source,
    )
    session.add(case)
    record_event(
        session,
        "resolution_applied",
        {"source": source, "resolution": resolution},
        bank_line_id=line.id,
        proposal_id=proposal.id,
        actor=reviewer or "system",
    )
    return case


def route_proposal(
    session: Session, proposal: Proposal, line: BankLine, settings: Settings
) -> None:
    """Authorize auto-application or put the recommendation in the review queue."""
    value = proposal_input(proposal)
    allowed, reason = policy_for(session, line, value, settings)
    proposal.policy_reason = reason
    if allowed:
        proposal.status = "auto_applied"
        apply_resolution(session, line, proposal, value, "agent_auto", settings=settings)
    else:
        line.status = "escalated" if value.decision == "escalate" else "in_review"
    record_event(
        session,
        "policy_decision",
        {"auto_apply": allowed, "reason": reason},
        bank_line_id=line.id,
        proposal_id=proposal.id,
    )
