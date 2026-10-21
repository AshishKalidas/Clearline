"""Clearline HTTP application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.api.activity import router as activity_router
from backend.app.api.dependencies import DB
from backend.app.api.ingest import router as ingest_router
from backend.app.api.invoices import router as invoices_router
from backend.app.api.pops import router as pops_router
from backend.app.api.reconciliation import router as reconciliation_router
from backend.app.ingest.validation import CsvInputError

app = FastAPI(title="Clearline", version="0.1.0")
app.include_router(ingest_router)
app.include_router(reconciliation_router)
app.include_router(pops_router)
app.include_router(invoices_router)
app.include_router(activity_router)


@app.exception_handler(CsvInputError)
async def csv_error(request: Request, exc: CsvInputError) -> JSONResponse:
    """Return only safe field diagnostics, never rejected CSV values."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
            "issues": [issue.model_dump() for issue in exc.issues],
            "issue_count": exc.issue_count,
        },
    )


@app.exception_handler(ValueError)
async def validation_error(request: Request, exc: ValueError) -> JSONResponse:
    """Return safe validation errors without echoing uploaded financial text."""
    return JSONResponse(
        status_code=422, content={"detail": "Invalid input", "error": type(exc).__name__}
    )


@app.get("/healthz")
def healthz(session: DB) -> dict[str, str]:
    """Check process liveness and database connectivity."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "service": "clearline"}
