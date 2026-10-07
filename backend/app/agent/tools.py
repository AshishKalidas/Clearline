"""Read-only investigation tools. No tool can mutate the ledger."""

from datetime import timedelta
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agent.schemas import (
    Arguments,
    CustomerArgs,
    CustomerSearch,
    HistoryArgs,
    InvoiceArgs,
    RunbookArgs,
    SearchInvoices,
    SimilarArgs,
)
from backend.app.db.models import Allocation, BankLine, Customer, Invoice, PopDocument
from backend.app.matching.rules import normalize_reference
from backend.app.retrieval.index import search_runbook, similar_cases


def invoice_data(invoice: Invoice) -> dict[str, Any]:
    """Expose only relevant invoice facts to the model and review screen."""
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "issue_date": str(invoice.issue_date),
        "due_date": str(invoice.due_date),
        "amount_cents": invoice.amount_cents,
        "outstanding_cents": invoice.outstanding_cents,
        "status": invoice.status,
    }


class ToolExecutor:
    """A bank-line-scoped read interface; submit is handled by the loop."""

    def __init__(self, session: Session, line: BankLine) -> None:
        self.session = session
        self.line = line

    def execute(self, name: str, args: Arguments) -> Any:
        """Dispatch previously validated tool arguments."""
        if name == "search_invoices" and isinstance(args, SearchInvoices):
            return self.search_invoices(args)
        if name == "get_invoice" and isinstance(args, InvoiceArgs):
            invoice = self.session.scalar(
                select(Invoice).where(Invoice.invoice_number == args.invoice_number)
            )
            if invoice is None:
                return {"error": "invoice_not_found"}
            data = invoice_data(invoice)
            data["allocations"] = [
                {"amount_cents": a.amount_cents, "source": a.source}
                for a in self.session.scalars(
                    select(Allocation).where(Allocation.invoice_id == invoice.id)
                )
            ]
            return data
        if name == "find_customers" and isinstance(args, CustomerSearch):
            return self.find_customers(args.name_query)
        if name == "get_customer" and isinstance(args, CustomerArgs):
            customer = self.session.get(Customer, args.customer_id)
            if customer is None:
                return {"error": "customer_not_found"}
            balance = (
                self.session.scalar(
                    select(func.sum(Invoice.outstanding_cents)).where(
                        Invoice.customer_id == customer.id
                    )
                )
                or 0
            )
            return {
                "id": customer.id,
                "account_code": customer.account_code,
                "name": customer.name,
                "notes": customer.notes,
                "open_balance_cents": balance,
            }
        if name == "get_payment_history" and isinstance(args, HistoryArgs):
            query = (
                select(Allocation, BankLine, Invoice)
                .join(BankLine, Allocation.bank_line_id == BankLine.id)
                .join(Invoice, Allocation.invoice_id == Invoice.id)
                .where(Invoice.customer_id == args.customer_id)
                .order_by(BankLine.value_date.desc())
                .limit(args.limit)
            )
            return [
                {
                    "bank_line_id": line.id,
                    "value_date": str(line.value_date),
                    "invoice_number": invoice.invoice_number,
                    "amount_cents": allocation.amount_cents,
                    "source": allocation.source,
                }
                for allocation, line, invoice in self.session.execute(query)
            ]
        if name == "find_duplicate_candidates":
            return self.duplicate_candidates()
        if name == "get_pop_verification":
            invoices = self.search_invoices(SearchInvoices(reference_like=self.line.raw_reference))
            ids = [i["id"] for i in invoices]
            pops = self.session.scalars(
                select(PopDocument).where(
                    (PopDocument.matched_bank_line_id == self.line.id)
                    | PopDocument.claimed_invoice_id.in_(ids)
                )
            ).all()
            return [{"id": p.id, "verdict": p.verdict, "checks": p.checks_json} for p in pops]
        if name == "find_similar_cases" and isinstance(args, SimilarArgs):
            return similar_cases(self.session, self.line, args.k, args.customer_id)
        if name == "search_runbook" and isinstance(args, RunbookArgs):
            return search_runbook(self.session, args.query, args.k)
        raise ValueError("Unknown tool or argument type")

    def search_invoices(self, args: SearchInvoices) -> list[dict[str, Any]]:
        """Filter open invoices without loading ground truth or modifying balances."""
        query = select(Invoice).where(Invoice.outstanding_cents > 0)
        if args.customer_id:
            query = query.where(Invoice.customer_id == args.customer_id)
        if args.amount_cents is not None:
            query = query.where(
                Invoice.outstanding_cents.between(
                    args.amount_cents - args.tolerance_cents,
                    args.amount_cents + args.tolerance_cents,
                )
            )
        if args.reference_like:
            query = query.where(Invoice.invoice_number.ilike(f"%{args.reference_like.strip()}%"))
        if args.date_from:
            query = query.where(Invoice.issue_date >= args.date_from)
        if args.date_to:
            query = query.where(Invoice.issue_date <= args.date_to)
        return [
            invoice_data(i)
            for i in self.session.scalars(
                query.order_by(Invoice.issue_date, Invoice.invoice_number).limit(100)
            )
        ]

    def find_customers(self, query: str) -> list[dict[str, Any]]:
        """Prefer exact identities; use PostgreSQL trigram similarity for fuzzy lookup."""
        exact = self.session.scalars(
            select(Customer).where(func.lower(Customer.name) == query.lower())
        ).all()
        if exact:
            pairs = [(c, 1.0) for c in exact]
        elif self.session.get_bind().dialect.name == "postgresql":
            score = func.similarity(Customer.name, query)
            pairs = [
                (c, float(s))
                for c, s in self.session.execute(
                    select(Customer, score).where(score > 0.35).order_by(score.desc()).limit(5)
                )
            ]
        else:
            pairs = [
                (c, SequenceMatcher(None, query.lower(), c.name.lower()).ratio())
                for c in self.session.scalars(select(Customer))
            ]
            pairs = sorted(
                (pair for pair in pairs if pair[1] > 0.35), key=lambda p: p[1], reverse=True
            )[:5]
        return [
            {"id": c.id, "account_code": c.account_code, "name": c.name, "score": round(score, 4)}
            for c, score in pairs
        ]

    def duplicate_candidates(self) -> list[dict[str, Any]]:
        """Find prior settled transfers with equal amount and normalized payer within seven days."""
        query = select(BankLine).where(
            BankLine.id != self.line.id,
            BankLine.status == "matched",
            BankLine.amount_cents == self.line.amount_cents,
            BankLine.value_date.between(
                self.line.value_date - timedelta(days=7), self.line.value_date
            ),
        )
        return [
            {
                "id": p.id,
                "value_date": str(p.value_date),
                "amount_cents": p.amount_cents,
                "reference": p.raw_reference,
            }
            for p in self.session.scalars(query)
            if normalize_reference(p.payer_name) == normalize_reference(self.line.payer_name)
        ]
