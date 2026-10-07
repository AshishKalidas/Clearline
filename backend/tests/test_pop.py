from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import BankLine
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from backend.app.matching.service import snapshot
from backend.app.pop.extract import PaymentClaim, extract_pdf, parse_money
from backend.app.pop.generate import generate_pdf, generate_pop_set, money
from backend.app.pop.verify import verify_claim
from evals.generate_dataset import csv_bytes, generate


def test_sixty_pdf_verdicts_and_reproducibility(session: Session, tmp_path: Path) -> None:
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    labels = generate_pop_set(tmp_path / "a", dataset)
    generate_pop_set(tmp_path / "b", dataset)
    lines = [snapshot(line) for line in session.scalars(select(BankLine))]
    actual = []
    for label in labels:
        content = (tmp_path / "a" / label["filename"]).read_bytes()
        assert content == (tmp_path / "b" / label["filename"]).read_bytes()
        claim = extract_pdf(content)
        assert claim is not None
        verdict = verify_claim(claim, lines, label["claimed_invoice_number"])
        assert verdict.verdict == label["verdict"], (label, verdict)
        actual.append(verdict.verdict)
        if verdict.verdict == "verified":
            assert all(c["passed"] for c in verdict.checks)
        else:
            assert not all(c["passed"] for c in verdict.checks)
    assert Counter(actual) == {"verified": 30, "not_received": 15, "mismatch": 15}


def test_upload_retrieve_unreadable(
    client: TestClient, session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POP_DIRECTORY", str(tmp_path / "stored"))
    from backend.app.config import get_settings

    get_settings.cache_clear()
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    labels = generate_pop_set(tmp_path / "proofs", dataset)
    content = (tmp_path / "proofs" / labels[0]["filename"]).read_bytes()
    headers = {"X-API-Key": "clearline-local-demo"}
    response = client.post(
        "/pops",
        headers=headers,
        files={"file": ("../../secret.pdf", content, "application/pdf")},
        data={"claimed_invoice_number": labels[0]["claimed_invoice_number"]},
    )
    assert response.status_code == 200 and response.json()["verdict"] == "verified"
    result = response.json()
    assert "secret" not in result["filename"]
    assert (tmp_path / "stored" / result["filename"]).exists()
    assert client.get(f"/pops/{result['id']}").json()["verdict"] == "verified"
    assert (
        client.post("/pops", headers=headers, files={"file": ("bad.pdf", b"%PDF broken")}).json()[
            "verdict"
        ]
        == "unreadable"
    )
    assert (
        client.post(
            "/pops",
            headers=headers,
            files={"file": ("bad.pdf", content)},
            data={"claimed_invoice_number": "INV-999999"},
        ).status_code
        == 422
    )
    assert client.get("/pops/missing").status_code == 404
    assert extract_pdf(b"not pdf") is None
    assert verify_claim(None, []).verdict == "unreadable"


def test_verification_tolerances_and_beneficiary() -> None:
    from backend.app.matching.rules import LineSnapshot

    day = date(2026, 9, 1)
    claim = PaymentClaim(12345, day, "INV-100003", "Lumen", "0042")
    line = LineSnapshot("bank", day + timedelta(days=2), 12345, "Lumen", "INV 100003")
    assert verify_claim(claim, [line]).verdict == "verified"
    assert verify_claim(claim, [line], beneficiary_last4="0000").verdict == "mismatch"
    assert verify_claim(claim, [line], claimed_invoice_number="INV-100006").verdict == "mismatch"
    assert verify_claim(claim, []).verdict == "not_received"
    assert parse_money("R 1 234,56") == 123456
    assert parse_money("ZAR 1,234.56") == 123456
    assert money(123456) == "R 1,234.56"
    assert money(-12345) == "-R 123.45"
    with pytest.raises(ValueError):
        parse_money("1.234.567")


def test_missing_and_duplicate_fields(tmp_path: Path) -> None:
    path = tmp_path / "claim.pdf"
    generate_pdf(
        path,
        {
            "amount_cents": 1,
            "payment_date": "not-a-date",
            "reference": "INV-100003",
            "payer_name": "Lumen",
        },
    )
    assert extract_pdf(path.read_bytes()) is None
