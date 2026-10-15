"""Clearline HTTP application."""

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.activity import router as activity_router
from backend.app.api.ingest import router as ingest_router
from backend.app.api.invoices import router as invoices_router
from backend.app.api.pops import router as pops_router
from backend.app.api.reconciliation import router as reconciliation_router
from backend.app.db.session import get_session

app = FastAPI(title="Clearline", version="0.1.0")
app.include_router(ingest_router)
app.include_router(reconciliation_router)
app.include_router(pops_router)
app.include_router(invoices_router)
app.include_router(activity_router)


@app.exception_handler(ValueError)
async def validation_error(request: Request, exc: ValueError) -> JSONResponse:
    """Return safe validation errors without echoing uploaded financial text."""
    return JSONResponse(
        status_code=422, content={"detail": "Invalid input", "error": type(exc).__name__}
    )


@app.get("/healthz")
def healthz(session: Session = Depends(get_session)) -> dict[str, str]:
    """Check process liveness and database connectivity."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "service": "clearline"}
