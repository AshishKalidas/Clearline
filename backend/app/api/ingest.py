"""CSV upload endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.app.api.dependencies import DB, require_key
from backend.app.config import get_settings
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices

router = APIRouter(prefix="/ingest", dependencies=[Depends(require_key)])


async def read_upload(file: UploadFile) -> bytes:
    """Read a bounded upload; never trust the filename or content-length header."""
    content = await file.read(get_settings().max_upload_bytes + 1)
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(413, "Upload exceeds the size limit")
    return content


@router.post("/invoices")
async def invoices(file: UploadFile, session: DB) -> dict[str, int]:
    """Import invoices and customers from UTF-8 CSV."""
    return ingest_invoices(session, await read_upload(file))


@router.post("/bank-lines")
async def bank_lines(file: UploadFile, session: DB) -> dict[str, int]:
    """Import bank lines with idempotent transaction hashes."""
    return ingest_bank_lines(session, await read_upload(file))
