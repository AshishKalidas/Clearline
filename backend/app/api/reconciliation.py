"""Reconciliation runs, review queue, human decisions and operational metrics."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from backend.app.agent.llm.stub import StubLLM
from backend.app.agent.loop import investigate
from backend.app.agent.schemas import ProposalInput
from backend.app.agent.service import apply_resolution, proposal_input
from backend.app.api.dependencies import DB, require_key, reviewer
from backend.app.audit.service import record_event
from backend.app.config import get_settings
from backend.app.db.models import AuditEvent, BankLine, Proposal, ResolvedCase
from backend.app.matching.service import run_rules

router = APIRouter()


def serialize_line(line: BankLine) -> dict[str, Any]:
    """Project a bank line for review."""
    return {
        "id": line.id,
        "value_date": str(line.value_date),
        "amount_cents": line.amount_cents,
        "raw_reference": line.raw_reference,
        "payer_name": line.payer_name,
        "payer_account_masked": line.payer_account_masked,
        "status": line.status,
    }


def serialize_proposal(proposal: Proposal, line: BankLine) -> dict[str, Any]:
    """Expose policy and human decision metadata alongside the bank evidence."""
    return {
        "id": proposal.id,
        "bank_line": serialize_line(line),
        "decision": proposal.decision,
        "allocations": proposal.allocations_json,
        "confidence": proposal.confidence,
        "reasoning": proposal.reasoning,
        "risk_flags": proposal.risk_flags,
        "status": proposal.status,
        "policy_reason": proposal.policy_reason,
        "evidence": proposal.evidence_json,
        "reviewer": proposal.reviewer,
        "review_note": proposal.review_note,
        "model": proposal.model,
        "prompt_tokens": proposal.prompt_tokens,
        "completion_tokens": proposal.completion_tokens,
        "latency_ms": proposal.latency_ms,
        "steps": proposal.steps,
    }


def lock_workflow(session: DB) -> None:
    """Serialize bank/invoice mutations across processes in PostgreSQL."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(724193)"))


@router.post("/runs/reconcile", dependencies=[Depends(require_key)])
async def reconcile(session: DB) -> dict[str, Any]:
    """Apply rules, then investigate every remaining exception with bounded calls."""
    lock_workflow(session)
    counts = run_rules(session)
    lines = session.scalars(
        select(BankLine)
        .where(BankLine.status == "unmatched")
        .order_by(BankLine.value_date, BankLine.id)
        .with_for_update()
    ).all()
    for line in lines:
        await investigate(session, line, StubLLM(), get_settings())
    return {"rules": counts, "agent_cases": len(lines)}


@router.get("/bank-lines")
def bank_lines(
    session: DB, status: str | None = None, limit: int = Query(500, ge=1, le=1000)
) -> list[dict[str, Any]]:
    """List bank observations, optionally filtered by workflow status."""
    query = select(BankLine)
    if status:
        query = query.where(BankLine.status == status)
    return [
        serialize_line(line)
        for line in session.scalars(query.order_by(BankLine.value_date.desc()).limit(limit))
    ]


@router.get("/proposals")
def proposals(session: DB, status: str = "pending") -> list[dict[str, Any]]:
    """List proposals sorted by largest payment first."""
    query = (
        select(Proposal, BankLine)
        .join(BankLine)
        .where(Proposal.status == status)
        .order_by(BankLine.amount_cents.desc(), Proposal.id)
        .limit(1000)
    )
    return [serialize_proposal(p, line) for p, line in session.execute(query)]


@router.get("/audit/{bank_line_id}")
def audit(bank_line_id: str, session: DB) -> list[dict[str, Any]]:
    """Read the complete ordered append-only trace for a bank line."""
    if session.get(BankLine, bank_line_id) is None:
        raise HTTPException(404, "Bank line not found")
    query = (
        select(AuditEvent)
        .where(AuditEvent.bank_line_id == bank_line_id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    )
    return [
        {
            "id": e.id,
            "actor": e.actor,
            "event_type": e.event_type,
            "created_at": e.created_at.isoformat(),
            "payload": e.payload_json,
        }
        for e in session.scalars(query)
    ]


@router.get("/proposals/{proposal_id}")
def proposal_detail(proposal_id: str, session: DB) -> dict[str, Any]:
    """Return a proposal with the exact tool evidence seen by the agent."""
    proposal = session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    line = session.get(BankLine, proposal.bank_line_id)
    assert line is not None
    data = serialize_proposal(proposal, line)
    data["trace"] = audit(line.id, session)
    return data


class ReviewBody(BaseModel):
    """An optional approval note and optional human-corrected resolution."""

    note: str = Field(default="", max_length=3000)
    corrected_resolution: ProposalInput | None = None


def pending(proposal_id: str, session: DB) -> tuple[Proposal, BankLine]:
    """Lock and reject stale or repeated human decisions."""
    lock_workflow(session)
    proposal = session.get(Proposal, proposal_id, with_for_update=True)
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(409, "Proposal has already been reviewed")
    line = session.get(BankLine, proposal.bank_line_id, with_for_update=True)
    assert line is not None
    return proposal, line


@router.post("/proposals/{proposal_id}/approve", dependencies=[Depends(require_key)])
def approve(
    proposal_id: str, body: ReviewBody, session: DB, identity: Annotated[str, Depends(reviewer)]
) -> dict[str, Any]:
    """Revalidate and apply the reviewer's decision once, atomically."""
    proposal, line = pending(proposal_id, session)
    value = body.corrected_resolution or proposal_input(proposal)
    proposal.status, proposal.reviewer, proposal.review_note = "approved", identity, body.note
    apply_resolution(session, line, proposal, value, "human", identity)
    record_event(
        session,
        "human_approved",
        {"note": body.note, "corrected": body.corrected_resolution is not None},
        bank_line_id=line.id,
        proposal_id=proposal.id,
        actor=identity,
    )
    return serialize_proposal(proposal, line)


@router.post("/proposals/{proposal_id}/reject", dependencies=[Depends(require_key)])
def reject(
    proposal_id: str, body: ReviewBody, session: DB, identity: Annotated[str, Depends(reviewer)]
) -> dict[str, Any]:
    """Reject with a required note; optionally apply a validated human correction."""
    if not body.note.strip():
        raise HTTPException(422, "A rejection note is required")
    proposal, line = pending(proposal_id, session)
    proposal.status, proposal.reviewer, proposal.review_note = "rejected", identity, body.note
    if body.corrected_resolution:
        apply_resolution(session, line, proposal, body.corrected_resolution, "human", identity)
    else:
        line.status = "escalated"
        session.add(
            ResolvedCase(
                bank_line_id=line.id,
                summary_text=f"Rejected: {body.note}",
                resolution_json={"decision": "escalate", "note": body.note},
                resolved_by="human",
            )
        )
    record_event(
        session,
        "human_rejected",
        {
            "note": body.note,
            "correction": body.corrected_resolution.model_dump(mode="json")
            if body.corrected_resolution
            else None,
        },
        bank_line_id=line.id,
        proposal_id=proposal.id,
        actor=identity,
    )
    return serialize_proposal(proposal, line)


@router.get("/metrics")
def metrics(session: DB) -> dict[str, Any]:
    """Return database-derived counts and usage, never fabricated model metrics."""
    counts = {
        status: count
        for status, count in session.execute(
            select(BankLine.status, func.count()).group_by(BankLine.status)
        )
    }
    proposal_counts = {
        status: count
        for status, count in session.execute(
            select(Proposal.status, func.count()).group_by(Proposal.status)
        )
    }
    usage = session.execute(
        select(
            func.avg(Proposal.latency_ms),
            func.sum(Proposal.prompt_tokens),
            func.sum(Proposal.completion_tokens),
        )
    ).one()
    total_proposals = sum(proposal_counts.values())
    return {
        "bank_lines": counts,
        "proposals": proposal_counts,
        "auto_apply_rate": proposal_counts.get("auto_applied", 0) / max(1, total_proposals),
        "mean_latency_ms": float(usage[0] or 0),
        "prompt_tokens": usage[1] or 0,
        "completion_tokens": usage[2] or 0,
        "provider": get_settings().llm_provider,
        "retrieval_enabled": get_settings().retrieval_enabled,
    }
