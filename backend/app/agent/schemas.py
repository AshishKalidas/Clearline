"""Provider-independent validated tool arguments and terminal proposal schema."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["match", "partial", "split", "overpayment", "duplicate", "escalate"]


class Arguments(BaseModel):
    """Reject unexpected fields in tool calls."""

    model_config = ConfigDict(extra="forbid")


class EmptyArgs(Arguments):
    """A tool with no caller-controlled parameters."""


class SearchInvoices(Arguments):
    """Search filters for open invoices."""

    customer_id: str | None = None
    amount_cents: int | None = Field(default=None, strict=True, ge=0)
    tolerance_cents: int = Field(default=0, strict=True, ge=0, le=50000)
    reference_like: str | None = Field(default=None, max_length=200)
    date_from: date | None = None
    date_to: date | None = None


class InvoiceArgs(Arguments):
    """Lookup an invoice by its public business identifier."""

    invoice_number: str = Field(pattern=r"^INV-\d{6}$")


class CustomerArgs(Arguments):
    """Lookup a customer by UUID."""

    customer_id: str = Field(min_length=1, max_length=36)


class CustomerSearch(Arguments):
    """A bounded fuzzy customer search."""

    name_query: str = Field(min_length=1, max_length=200)


class HistoryArgs(CustomerArgs):
    """Bounded historical-payment lookup."""

    limit: int = Field(default=10, ge=1, le=50)


class SimilarArgs(Arguments):
    """Bounded case retrieval, optionally filtered by candidate customer."""

    k: int = Field(default=5, ge=1, le=20)
    customer_id: str | None = None


class RunbookArgs(Arguments):
    """Bounded retrieval from the fictional policy runbook."""

    query: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)


class AllocationInput(Arguments):
    """One allocation, in integer cents."""

    invoice_number: str = Field(pattern=r"^INV-\d{6}$")
    amount_cents: int = Field(gt=0, strict=True, le=10**12)


class ProposalInput(Arguments):
    """The model's only permitted write: a structured recommendation."""

    decision: Decision
    allocations: list[AllocationInput] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    reasoning: str = Field(min_length=1, max_length=5000)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    risk_flags: list[str] = Field(default_factory=list, max_length=20)


TOOL_MODELS: dict[str, type[Arguments]] = {
    "search_invoices": SearchInvoices,
    "get_invoice": InvoiceArgs,
    "find_customers": CustomerSearch,
    "get_customer": CustomerArgs,
    "get_payment_history": HistoryArgs,
    "find_similar_cases": SimilarArgs,
    "search_runbook": RunbookArgs,
    "find_duplicate_candidates": EmptyArgs,
    "get_pop_verification": EmptyArgs,
    "submit_proposal": ProposalInput,
}


def tool_schemas() -> list[dict[str, object]]:
    """Define tool schemas once; provider adapters translate only their envelope."""
    return [
        {
            "name": name,
            "description": model.__doc__ or name,
            "parameters": model.model_json_schema(),
        }
        for name, model in TOOL_MODELS.items()
    ]
