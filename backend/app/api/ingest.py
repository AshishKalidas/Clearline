"""CSV upload endpoints."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.app.api.dependencies import DB, require_key
from backend.app.audit.service import record_event
from backend.app.config import get_settings
from backend.app.db.session import lock_workflow
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from backend.app.ingest.validation import ImportKind, ImportPreview, preview_csv

router = APIRouter(prefix="/ingest", dependencies=[Depends(require_key)])


async def read_upload(file: UploadFile) -> bytes:
    """Read a bounded upload; never trust the filename or content-length header."""
    content = await file.read(get_settings().max_upload_bytes + 1)
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(413, "Upload exceeds the size limit")
    return content


@router.post("/{kind}/preview")
async def preview(kind: ImportKind, file: UploadFile) -> ImportPreview:
    """Validate the entire CSV without opening a database transaction or changing records."""
    return preview_csv(kind, await read_upload(file))


@router.post("/invoices")
async def invoices(file: UploadFile, session: DB) -> dict[str, int]:
    """Import invoices and customers from UTF-8 CSV."""
    content = await read_upload(file)
    lock_workflow(session)
    result = ingest_invoices(session, content)
    record_event(
        session, "invoices_ingested", {**result, "sha256": hashlib.sha256(content).hexdigest()}
    )
    return result


@router.post("/bank-lines")
async def bank_lines(file: UploadFile, session: DB) -> dict[str, int]:
    """Import bank lines with idempotent transaction hashes."""
    content = await read_upload(file)
    lock_workflow(session)
    result = ingest_bank_lines(session, content)
    record_event(
        session, "bank_lines_ingested", {**result, "sha256": hashlib.sha256(content).hexdigest()}
    )
    return result
