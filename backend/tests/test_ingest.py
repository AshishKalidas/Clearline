import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import BankLine, Invoice
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices, parse_csv
from evals.generate_dataset import SCENARIOS, csv_bytes, generate, write_dataset


def test_generator_byte_reproducible(tmp_path: Path) -> None:
    write_dataset(tmp_path / "a")
    write_dataset(tmp_path / "b")
    for path in (tmp_path / "a").iterdir():
        assert path.read_bytes() == (tmp_path / "b" / path.name).read_bytes()
    labels = json.loads((tmp_path / "a/labels.json").read_text())
    assert Counter(x["scenario"] for x in labels) == {
        s: share * 4 for s, share in SCENARIOS.items()
    }
    assert len(generate()["history"]) == 300
    assert generate(43) != generate(42)
    with pytest.raises(ValueError):
        generate(cases=12)


def test_idempotent_ingest(session: Session) -> None:
    dataset = generate()
    inv = csv_bytes(dataset["invoices"])
    bank = csv_bytes(dataset["bank_lines"])
    first = ingest_invoices(session, inv)
    assert first["inserted"] == len(dataset["invoices"])
    assert ingest_invoices(session, inv)["inserted"] == 0
    assert ingest_bank_lines(session, bank)["inserted"] == 400
    assert ingest_bank_lines(session, bank)["inserted"] == 0
    assert session.scalar(select(func.count()).select_from(BankLine)) == 400
    assert session.scalar(select(func.count()).select_from(Invoice)) == first["inserted"]


def test_csv_errors_and_authenticated_api(client: TestClient) -> None:
    with pytest.raises(ValueError):
        parse_csv(b"a,b\n")
    with pytest.raises(ValueError):
        parse_csv(b"a,b\n1,2,3\n")
    inv = csv_bytes(generate()["invoices"])
    assert client.post("/ingest/invoices", files={"file": ("invoices.csv", inv)}).status_code == 401
    headers = {"X-API-Key": "clearline-local-demo"}
    response = client.post(
        "/ingest/invoices", headers=headers, files={"file": ("invoices.csv", inv)}
    )
    assert response.status_code == 200
    assert response.json()["inserted"] == len(generate()["invoices"])
    assert (
        client.post(
            "/ingest/invoices", headers=headers, files={"file": ("bad.csv", b"bad")}
        ).status_code
        == 422
    )
