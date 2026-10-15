from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import Allocation, AuditEvent, BankLine


def test_activity_is_bounded_masked_and_chronological(client: TestClient, session: Session) -> None:
    line = BankLine(
        value_date=date(2026, 9, 2),
        amount_cents=100000001,
        payer_name="Synthetic payer fictional@example.invalid 9999999999999",
        payer_account_masked="0042",
        raw_reference="INV-100001",
        line_hash="activity-fixture",
    )
    session.add(line)
    session.flush()
    start = datetime(2026, 9, 2, 12, tzinfo=UTC)
    for n, kind in enumerate(["rules_match", "human_approved", "tool_call"]):
        session.add(
            AuditEvent(
                bank_line_id=line.id,
                actor="synthetic reviewer",
                event_type=kind,
                payload_json={"internal_payload": "excluded from the activity projection"},
                created_at=start + timedelta(seconds=n),
            )
        )
    session.commit()
    response = client.get("/activity?limit=1")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1 and rows[0]["event_type"] == "human_approved"
    assert rows[0]["created_at"].endswith("+00:00")
    assert rows[0]["amount_cents"] == 100000001
    assert "fictional@example.invalid" not in response.text and "9999999999999" not in response.text
    assert "[EMAIL_1]" in response.text and "[ID_1]" in response.text
    assert "payload" not in response.text
    assert [row["event_type"] for row in client.get("/activity").json()] == [
        "human_approved",
        "rules_match",
    ]
    assert client.get("/activity?limit=101").status_code == 422
    assert client.get("/activity?limit=0").status_code == 422
    assert session.scalar(select(func.count()).select_from(Allocation)) == 0
