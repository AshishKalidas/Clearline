from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.models import BankLine


def test_bank_evidence_remains_addressable_outside_the_feed_limit(
    client: TestClient, session: Session
) -> None:
    start = date(2020, 1, 1)
    session.add_all(
        BankLine(
            id=f"bank-{index}",
            value_date=start + timedelta(days=index),
            amount_cents=12345,
            payer_name="Synthetic payer",
            raw_reference="INV-100003",
            payer_account_masked="0042",
            line_hash=f"hash-{index}",
        )
        for index in range(1001)
    )
    session.commit()

    feed = client.get("/bank-lines?limit=1000")
    assert feed.status_code == 200
    assert len(feed.json()) == 1000
    assert all(line["id"] != "bank-0" for line in feed.json())

    evidence = client.get("/bank-lines/bank-0")
    assert evidence.status_code == 200
    assert evidence.json() == {
        "id": "bank-0",
        "value_date": str(start),
        "amount_cents": 12345,
        "payer_name": "Synthetic payer",
        "raw_reference": "INV-100003",
        "payer_account_masked": "0042",
        "status": "unmatched",
    }


def test_unknown_bank_observation_returns_not_found(client: TestClient) -> None:
    response = client.get("/bank-lines/missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Bank line not found"}
