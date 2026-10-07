from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agent.schemas import (
    CustomerArgs,
    CustomerSearch,
    EmptyArgs,
    HistoryArgs,
    InvoiceArgs,
    SearchInvoices,
)
from backend.app.agent.tools import ToolExecutor
from backend.app.db.models import BankLine, Invoice, PopDocument
from backend.app.ingest.service import ingest_bank_lines, ingest_invoices
from backend.app.matching.service import run_rules
from evals.generate_dataset import csv_bytes, generate


def test_read_only_tool_filters_and_evidence(session: Session) -> None:
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    run_rules(session)
    line = session.get(BankLine, dataset["labels"][160]["bank_line_id"])
    assert line is not None
    tool = ToolExecutor(session, line)
    customer = tool.execute("find_customers", CustomerSearch(name_query=line.payer_name))[0]
    invoices = tool.execute("search_invoices", SearchInvoices(customer_id=customer["id"]))
    assert len(invoices) == 1
    number = invoices[0]["invoice_number"]
    assert tool.execute("get_invoice", InvoiceArgs(invoice_number=number))["allocations"] == []
    assert (
        tool.execute("get_customer", CustomerArgs(customer_id=customer["id"]))["open_balance_cents"]
        == line.amount_cents
    )
    assert (
        tool.execute("get_customer", CustomerArgs(customer_id="missing"))["error"]
        == "customer_not_found"
    )
    assert (
        tool.execute("get_invoice", InvoiceArgs(invoice_number="INV-999999"))["error"]
        == "invoice_not_found"
    )
    assert tool.execute("get_payment_history", HistoryArgs(customer_id=customer["id"])) == []
    assert tool.execute(
        "search_invoices",
        SearchInvoices(
            customer_id=customer["id"],
            amount_cents=line.amount_cents,
            tolerance_cents=0,
            reference_like=number,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
        ),
    )
    assert (
        tool.execute(
            "search_invoices",
            SearchInvoices(customer_id=customer["id"], amount_cents=line.amount_cents + 1),
        )
        == []
    )
    assert tool.execute("find_customers", CustomerSearch(name_query=line.payer_name[:-1]))
    with pytest.raises(ValueError):
        tool.execute("write_invoice", EmptyArgs())
    assert not session.dirty and not session.new


def test_history_and_linked_pop(session: Session) -> None:
    dataset = generate()
    ingest_invoices(session, csv_bytes(dataset["invoices"]))
    ingest_bank_lines(session, csv_bytes(dataset["bank_lines"]))
    run_rules(session)
    line = session.get(BankLine, dataset["labels"][40]["bank_line_id"])
    assert line is not None
    tool = ToolExecutor(session, line)
    invoice = session.scalar(select(Invoice).where(Invoice.invoice_number == line.raw_reference))
    assert invoice is not None
    assert (
        tool.execute("get_payment_history", HistoryArgs(customer_id=invoice.customer_id))[0][
            "source"
        ]
        == "rules"
    )
    assert tool.execute("get_invoice", InvoiceArgs(invoice_number=invoice.invoice_number))[
        "allocations"
    ]
    session.add(
        PopDocument(
            filename="synthetic.pdf",
            claimed_invoice_id=invoice.id,
            matched_bank_line_id=line.id,
            extracted_json={},
            checks_json=[],
            verdict="mismatch",
        )
    )
    session.flush()
    assert tool.execute("get_pop_verification", EmptyArgs())[0]["verdict"] == "mismatch"
