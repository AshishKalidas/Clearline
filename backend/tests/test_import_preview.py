import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import AuditEvent, BankLine, Invoice
from backend.app.ingest.validation import CsvInputError, parse_csv, preview_csv
from evals.generate_dataset import csv_bytes, generate

KEY = {"X-API-Key": "clearline-local-demo"}


def test_preview_validates_every_record_without_mutating_or_calling_a_model(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Preview must not create a model client")

    monkeypatch.setattr("backend.app.agent.llm.factory.create_client", forbidden)
    content = csv_bytes(generate()["invoices"])
    assert (
        client.post("/ingest/invoices/preview", files={"file": ("test.csv", content)}).status_code
        == 401
    )
    response = client.post(
        "/ingest/invoices/preview", headers=KEY, files={"file": ("test.csv", content)}
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["row_count"] == len(generate()["invoices"])
    assert len(preview["rows"]) == 5
    assert type(preview["rows"][0]["amount_cents"]) is int
    assert session.scalar(select(func.count()).select_from(Invoice)) == 0
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    assert (
        client.post(
            "/ingest/unknown/preview", headers=KEY, files={"file": ("test.csv", content)}
        ).status_code
        == 422
    )


def test_preview_reports_safe_bounded_issues_including_records_after_the_sample(
    client: TestClient,
) -> None:
    rows = generate()["bank_lines"][:30]
    for row in rows[5:]:
        row["payer_account_masked"] = "secret-account-value"
        row["amount_cents"] = "secret-amount-value"
    content = csv_bytes(rows)
    response = client.post(
        "/ingest/bank-lines/preview", headers=KEY, files={"file": ("test.csv", content)}
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["issue_count"] == 50
    assert len(payload["issues"]) == 20
    assert payload["issues"][0]["row"] == 7
    assert (
        "secret-account-value" not in response.text and "secret-amount-value" not in response.text
    )
    assert "input" not in json.dumps(payload["issues"])


@pytest.mark.parametrize(
    "content",
    [
        b"value_date,value_date\n2026-09-02,2026-09-02\n",
        b"a,,b\n1,2,3\n",
        b"a,b\n1,2,3\n",
        b"a,b\n1\n",
        b"a,b\n\xff,2\n",
        b'a,b\n"unterminated,2\n',
        b"a,b\n",
    ],
)
def test_ambiguous_and_malformed_csv_is_rejected(content: bytes) -> None:
    with pytest.raises(CsvInputError):
        parse_csv(content)


def test_limits_bom_and_zero_value_validation() -> None:
    with pytest.raises(CsvInputError):
        parse_csv(b"a\n" + b"1\n" * 10001)
    bank = generate()["bank_lines"][:1]
    checked = preview_csv("bank-lines", b"\xef\xbb\xbf" + csv_bytes(bank))
    assert checked.row_count == 1
    bank[0]["amount_cents"] = 0
    with pytest.raises(CsvInputError):
        preview_csv("bank-lines", csv_bytes(bank))


def test_duplicate_import_is_counted_and_conflicts_roll_back_the_whole_file(
    client: TestClient, session: Session
) -> None:
    rows = generate()["invoices"][:2]
    content = csv_bytes(rows[:1])
    for expected in ({"inserted": 1, "skipped": 0}, {"inserted": 0, "skipped": 1}):
        response = client.post(
            "/ingest/invoices", headers=KEY, files={"file": ("test.csv", content)}
        )
        assert response.json() == expected
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2
    conflict = {**rows[0], "amount_cents": rows[0]["amount_cents"] + 1}
    response = client.post(
        "/ingest/invoices",
        headers=KEY,
        files={"file": ("conflict.csv", csv_bytes([rows[1], conflict]))},
    )
    assert response.status_code == 422
    assert response.json()["issues"][0]["row"] == 3
    assert session.scalar(select(func.count()).select_from(Invoice)) == 1
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2
    bank = csv_bytes(generate()["bank_lines"][:1])
    for expected in ({"inserted": 1, "skipped": 0}, {"inserted": 0, "skipped": 1}):
        response = client.post(
            "/ingest/bank-lines", headers=KEY, files={"file": ("test.csv", bank)}
        )
        assert response.json() == expected
    assert session.scalar(select(func.count()).select_from(BankLine)) == 1
