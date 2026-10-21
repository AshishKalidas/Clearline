import json
import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from backend.app.agent.schemas import CustomerArgs
from backend.app.agent.tools import ToolExecutor
from backend.app.audit.service import record_event
from backend.app.db.models import Customer, Invoice
from evals.run_eval import evaluation_session


def test_postgres_customer_aggregate_remains_integer_cents_and_can_be_audited() -> None:
    if not os.getenv("MIGRATION_DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL returns numeric for SUM(bigint); Docker verifies this boundary")
    with evaluation_session() as (session, _):
        customer = Customer(name="Synthetic aggregate customer", account_code="C-99991")
        session.add(customer)
        session.flush()
        session.add(
            Invoice(
                invoice_number="INV-999991",
                customer_id=customer.id,
                issue_date=date(2026, 9, 1),
                due_date=date(2026, 9, 30),
                amount_cents=12345,
                outstanding_cents=12345,
            )
        )
        session.flush()
        assert isinstance(session.scalar(select(func.sum(Invoice.outstanding_cents))), Decimal)
        result = ToolExecutor(session).execute(
            "get_customer", CustomerArgs(customer_id=customer.id)
        )
        assert type(result["open_balance_cents"]) is int
        assert result["open_balance_cents"] == 12345
        assert json.loads(json.dumps(result))["open_balance_cents"] == 12345
        record_event(session, "tool_call", {"tool": "get_customer", "result": result})
