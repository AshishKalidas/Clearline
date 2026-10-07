"""Proof uploads and plain-language bank-evidence verdicts."""

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select

from backend.app.api.dependencies import DB, require_key
from backend.app.api.ingest import read_upload
from backend.app.audit.service import record_event
from backend.app.config import get_settings
from backend.app.db.models import BankLine, Invoice, PopDocument
from backend.app.db.session import lock_workflow
from backend.app.matching.service import snapshot
from backend.app.pop.extract import extract_pdf
from backend.app.pop.verify import verify_claim
from backend.app.privacy.masking import Masker

router = APIRouter()


def pop_data(document: PopDocument) -> dict[str, Any]:
    """Serialize an extracted claim with its independent bank checks."""
    summary = {
        "verified": (
            "Bank evidence supports this payment claim. Review invoice settlement before dispatch."
        ),
        "not_received": "No matching payment has arrived in the bank feed. Do not release goods.",
        "mismatch": "This claim disagrees with bank evidence. Do not release goods.",
        "unreadable": "Required fields could not be extracted. Do not release goods.",
    }[document.verdict]
    return {
        "id": document.id,
        "filename": document.filename,
        "verdict": document.verdict,
        "extracted": document.extracted_json,
        "checks": document.checks_json,
        "matched_bank_line_id": document.matched_bank_line_id,
        "summary": summary,
    }


@router.post("/pops", dependencies=[Depends(require_key)])
async def upload_pop(
    file: UploadFile, session: DB, claimed_invoice_number: str | None = Form(default=None)
) -> dict[str, Any]:
    """Extract a bounded PDF and verify exclusively against received bank observations."""
    content = await read_upload(file)
    lock_workflow(session)
    invoice = None
    if claimed_invoice_number:
        invoice = session.scalar(
            select(Invoice).where(Invoice.invoice_number == claimed_invoice_number)
        )
        if invoice is None:
            raise HTTPException(422, "Claimed invoice does not exist")
    claim = await asyncio.to_thread(extract_pdf, content)
    lines = session.scalars(
        select(BankLine).where(BankLine.amount_cents > 0, BankLine.status != "reversed")
    ).all()
    verdict = verify_claim(claim, [snapshot(line) for line in lines], claimed_invoice_number)
    identifier = str(uuid4())
    directory = get_settings().pop_directory
    directory.mkdir(parents=True, exist_ok=True)
    # Filename never comes from the user: traversal and accidental PII are excluded.
    filename = f"{identifier}.pdf"
    (directory / filename).write_bytes(content)
    document = PopDocument(
        id=identifier,
        filename=filename,
        claimed_invoice_id=invoice.id if invoice else None,
        extracted_json=Masker().clean(claim.as_dict() if claim else {}),
        verdict=verdict.verdict,
        matched_bank_line_id=verdict.matched_bank_line_id,
        checks_json=Masker().clean(verdict.checks),
    )
    session.add(document)
    record_event(
        session,
        "pop_verified",
        {"pop_id": identifier, "verdict": verdict.verdict, "checks": verdict.checks},
        bank_line_id=verdict.matched_bank_line_id,
    )
    return {**pop_data(document), "summary": verdict.summary}


@router.get("/pops/{document_id}")
def get_pop(document_id: str, session: DB) -> dict[str, Any]:
    """Read a stored claim and its bank verification results."""
    document = session.get(PopDocument, document_id)
    if document is None:
        raise HTTPException(404, "Proof of payment not found")
    return pop_data(document)
