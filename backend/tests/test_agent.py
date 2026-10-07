import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agent.llm.base import ModelReply, ToolCall
from backend.app.agent.llm.stub import StubLLM
from backend.app.agent.loop import investigate
from backend.app.agent.policy import PolicyFacts, evaluate_policy
from backend.app.agent.schemas import ProposalInput
from backend.app.agent.validation import validate_proposal
from backend.app.config import Settings
from backend.app.db.models import (
    Allocation,
    AuditEvent,
    BankLine,
    Invoice,
    PopDocument,
    Proposal,
    ResolvedCase,
)
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from evals.generate_dataset import csv_bytes, generate


def load(session: Session) -> dict[str, Any]:
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    return dataset


def test_reconcile_and_safety_invariants(client: TestClient, session: Session) -> None:
    dataset = load(session)
    labels = {x["bank_line_id"]: x for x in dataset["labels"]}
    first_id = dataset["labels"][0]["bank_line_id"]
    for history in dataset["history"]:
        session.add(
            ResolvedCase(
                bank_line_id=first_id,
                customer_id=history["customer_id"],
                summary_text=history["summary_text"],
                resolution_json=history["resolution_json"],
                resolved_by="rules",
            )
        )
    session.commit()
    response = client.post("/runs/reconcile", headers={"X-API-Key": "clearline-local-demo"})
    assert response.status_code == 200, response.text
    assert response.json()["agent_cases"] == 228
    assert (
        session.scalar(
            select(func.count()).select_from(BankLine).where(BankLine.status == "unmatched")
        )
        == 0
    )
    for proposal in session.scalars(select(Proposal)):
        line = session.get(BankLine, proposal.bank_line_id)
        assert line is not None
        assert proposal.decision == labels[line.id]["decision"]
        assert (
            sorted(a["invoice_number"] for a in proposal.allocations_json)
            == labels[line.id]["invoices"]
        )
        tool_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.bank_line_id == line.id, AuditEvent.event_type == "tool_call"
            )
        ).all()
        assert len(tool_events) == proposal.steps
        if proposal.status == "auto_applied":
            assert proposal.decision == "match"
            assert line.amount_cents <= 500000
            assert not proposal.risk_flags
    for line in session.scalars(select(BankLine)):
        applied = (
            session.scalar(
                select(func.sum(Allocation.amount_cents)).where(Allocation.bank_line_id == line.id)
            )
            or 0
        )
        assert applied <= max(0, line.amount_cents)
    assert (
        client.post("/runs/reconcile", headers={"X-API-Key": "clearline-local-demo"}).json()[
            "agent_cases"
        ]
        == 0
    )


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"decision": "partial"}, "decision"),
        ({"confidence": 0.89}, "confidence"),
        ({"amount_cents": 500001}, "amount"),
        ({"amount_cents": -1}, "amount"),
        ({"risk_flags": ["risk"]}, "risk flags"),
        ({"pop_mismatch": True}, "proof"),
        ({"has_customer_history": False}, "prior resolved case"),
    ],
)
def test_policy_vetoes(override: dict[str, Any], reason: str) -> None:
    args = {
        "decision": "match",
        "confidence": 0.95,
        "amount_cents": 100,
        "risk_flags": [],
        "pop_mismatch": False,
        "has_customer_history": True,
    }
    args.update(override)
    allowed, explanation = evaluate_policy(PolicyFacts(**args), Settings())
    assert not allowed and reason in explanation


def test_policy_boundary() -> None:
    assert evaluate_policy(PolicyFacts("match", 0.9, 500000, [], False, True), Settings())[0]


class BrokenLLM:
    model = "recorded-test"

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        self.calls += 1
        if self.mode == "sleep":
            await asyncio.sleep(1)
        if self.mode == "error":
            raise RuntimeError("do not echo provider secrets")
        if self.mode == "empty":
            return ModelReply()
        if self.mode == "proposal":
            return ModelReply(
                [
                    ToolCall(
                        "p",
                        "submit_proposal",
                        {
                            "decision": "match",
                            "allocations": [{"invoice_number": "INV-999999", "amount_cents": 1}],
                            "confidence": 1,
                            "reasoning": "invented",
                            "evidence": [],
                            "risk_flags": [],
                        },
                    )
                ]
            )
        return ModelReply([ToolCall("x", "search_invoices", {"tolerance_cents": -1})])


@pytest.mark.parametrize(
    "mode,flag,steps",
    [
        ("invalid", "agent_limit_reached", 8),
        ("sleep", "agent_limit_reached", 0),
        ("error", "provider_error", 0),
        ("empty", "missing_terminal_proposal", 0),
        ("proposal", "proposal_validation_failed", 2),
    ],
)
def test_bounded_loop(session: Session, mode: str, flag: str, steps: int) -> None:
    dataset = load(session)
    line = session.get(BankLine, dataset["labels"][160]["bank_line_id"])
    assert line is not None
    proposal = asyncio.run(
        investigate(
            session, line, BrokenLLM(mode), Settings(), max_seconds=0.05 if mode == "sleep" else 5
        )
    )
    assert proposal.decision == "escalate"
    assert flag in proposal.risk_flags
    assert proposal.steps == steps
    assert session.scalar(select(func.count()).select_from(Allocation)) == 0


def test_review_approve_reject_correct(client: TestClient, session: Session) -> None:
    load(session)
    key = {"X-API-Key": "clearline-local-demo", "X-Reviewer": "Synthetic Reviewer"}
    client.post("/runs/reconcile", headers=key)
    queue = client.get("/proposals").json()
    assert queue
    match = next(p for p in queue if p["decision"] == "match")
    detail = client.get(f"/proposals/{match['id']}")
    assert detail.status_code == 200 and len(detail.json()["trace"]) >= 6
    url = f"/proposals/{match['id']}/approve"
    assert (
        client.post(url, headers={"X-API-Key": "clearline-local-demo"}, json={}).status_code == 422
    )
    assert client.post(url, headers=key, json={"note": "Verified bank evidence"}).status_code == 200
    assert client.post(url, headers=key, json={}).status_code == 409
    split = next(p for p in queue if p["decision"] == "split")
    reject = f"/proposals/{split['id']}/reject"
    assert client.post(reject, headers=key, json={}).status_code == 422
    correction = {
        k: split[k]
        for k in ("decision", "allocations", "confidence", "reasoning", "evidence", "risk_flags")
    }
    assert (
        client.post(
            reject,
            headers=key,
            json={"note": "Human verified the split", "corrected_resolution": correction},
        ).status_code
        == 200
    )
    unknown = next(p for p in queue if p["decision"] == "escalate")
    assert (
        client.post(
            f"/proposals/{unknown['id']}/reject", headers=key, json={"note": "Investigate payer"}
        ).status_code
        == 200
    )
    assert client.get("/metrics").json()["proposals"]["approved"] == 1
    assert client.get("/bank-lines?status=unmatched").json() == []
    assert client.get("/proposals/nonexistent").status_code == 404
    assert client.get("/audit/nonexistent").status_code == 404


def test_mismatch_override_and_invoice_choices(client: TestClient, session: Session) -> None:
    """A proof mismatch requires an explained human override, never a silent click."""
    dataset = load(session)
    label = dataset["labels"][160]
    invoice = session.scalar(select(Invoice).where(Invoice.invoice_number == label["invoices"][0]))
    assert invoice is not None
    session.add(
        PopDocument(
            filename="synthetic.pdf",
            claimed_invoice_id=invoice.id,
            extracted_json={},
            verdict="mismatch",
            checks_json=[],
        )
    )
    session.commit()
    key = {"X-API-Key": "clearline-local-demo", "X-Reviewer": "Synthetic Reviewer"}
    assert client.post("/runs/reconcile", headers=key).status_code == 200
    proposal = session.scalar(
        select(Proposal).where(Proposal.bank_line_id == label["bank_line_id"])
    )
    assert proposal is not None
    detail = client.get(f"/proposals/{proposal.id}").json()
    assert detail["linked_pops"][0]["verdict"] == "mismatch"
    choices = client.get("/invoices", params={"query": invoice.invoice_number}).json()
    assert choices[0]["id"] == invoice.id and choices[0]["customer_name"]
    url = f"/proposals/{proposal.id}/approve"
    assert client.post(url, headers=key, json={}).status_code == 422
    assert (
        session.scalar(
            select(Allocation.id).where(Allocation.bank_line_id == label["bank_line_id"])
        )
        is None
    )
    assert (
        client.post(
            url,
            headers=key,
            json={"note": "Confirmed independent bank evidence; investigated conflicting document"},
        ).status_code
        == 200
    )
    allocation = session.scalar(
        select(Allocation).where(Allocation.bank_line_id == label["bank_line_id"])
    )
    assert allocation is not None and allocation.source == "human"


def test_invalid_allocations_and_mismatch_rule_veto(session: Session) -> None:
    dataset = load(session)
    line = session.get(BankLine, dataset["labels"][0]["bank_line_id"])
    assert line is not None
    number = dataset["labels"][0]["invoices"][0]
    invoice = session.scalar(select(Invoice).where(Invoice.invoice_number == number))
    assert invoice is not None
    invalid = ProposalInput(
        decision="match",
        allocations=[{"invoice_number": number, "amount_cents": line.amount_cents + 1}],
        confidence=1,
        reasoning="invalid",
    )
    with pytest.raises(ValueError):
        validate_proposal(session, line, invalid)
    session.add(
        PopDocument(
            filename="synthetic.pdf",
            claimed_invoice_id=invoice.id,
            extracted_json={},
            verdict="mismatch",
            checks_json=[],
        )
    )
    session.flush()
    from backend.app.matching.service import run_rules

    run_rules(session)
    assert line.status == "unmatched"
    proposal = asyncio.run(investigate(session, line, StubLLM(), Settings()))
    assert proposal.status == "pending"
    assert "mismatch" in proposal.policy_reason
    assert session.scalar(select(Allocation.id).where(Allocation.bank_line_id == line.id)) is None
