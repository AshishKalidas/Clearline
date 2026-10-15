"""Bounded, masked audit summaries for the connected workspace's live panel."""

from datetime import UTC
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.app.api.dependencies import DB
from backend.app.db.models import AuditEvent, BankLine
from backend.app.privacy.masking import Masker

router = APIRouter()


@router.get("/activity")
def activity(session: DB, limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    """Return recent meaningful events without exposing full investigation payloads."""
    query = (
        select(AuditEvent, BankLine)
        .outerjoin(BankLine, AuditEvent.bank_line_id == BankLine.id)
        .where(AuditEvent.event_type != "tool_call")
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return Masker().clean(
        [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "created_at": (
                    event.created_at
                    if event.created_at.tzinfo
                    else event.created_at.replace(tzinfo=UTC)
                ).isoformat(),
                "bank_line_id": event.bank_line_id,
                "proposal_id": event.proposal_id,
                "payer_name": line.payer_name if line else None,
                "amount_cents": line.amount_cents if line else None,
            }
            for event, line in session.execute(query)
        ]
    )
