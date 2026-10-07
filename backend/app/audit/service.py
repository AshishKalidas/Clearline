"""Append audit evidence; callers cannot update or delete past events."""

from typing import Any

from sqlalchemy.orm import Session

from backend.app.db.models import AuditEvent


def record_event(
    session: Session,
    event_type: str,
    payload: dict[str, Any],
    *,
    bank_line_id: str | None = None,
    proposal_id: str | None = None,
    actor: str = "system",
) -> AuditEvent:
    """Append an event inside the caller's transaction."""
    event = AuditEvent(
        bank_line_id=bank_line_id,
        proposal_id=proposal_id,
        actor=actor,
        event_type=event_type,
        payload_json=payload,
    )
    session.add(event)
    session.flush()
    return event
