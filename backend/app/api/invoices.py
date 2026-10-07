"""Read-only invoice choices for a reviewer's corrected allocation."""

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.app.agent.tools import invoice_data
from backend.app.api.dependencies import DB
from backend.app.db.models import Customer, Invoice

router = APIRouter()


@router.get("/invoices")
def invoices(
    session: DB,
    query: str = Query(default="", max_length=100),
    limit: int = Query(default=1000, ge=1, le=1000),
) -> list[dict[str, Any]]:
    """List open balances with fictional customer labels for the correction picker."""
    statement = select(Invoice, Customer).join(Customer).where(Invoice.outstanding_cents > 0)
    if query:
        statement = statement.where(
            Invoice.invoice_number.ilike(f"%{query}%") | Customer.name.ilike(f"%{query}%")
        )
    return [
        {
            **invoice_data(invoice),
            "customer_name": customer.name,
            "account_code": customer.account_code,
        }
        for invoice, customer in session.execute(
            statement.order_by(Invoice.issue_date, Invoice.invoice_number).limit(limit)
        )
    ]
