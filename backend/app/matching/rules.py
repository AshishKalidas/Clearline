"""Pure rules; evidence must identify exactly one invoice or reversal."""

import re
from dataclasses import dataclass
from datetime import date

INJECTION = re.compile(r"ignore\s+rules|system\s*:|mark\s+as\s+paid|confidence\s+1\.0", re.I)


def has_injection(text: str) -> bool:
    """Detect the explicit instruction patterns in the synthetic threat set."""
    return bool(INJECTION.search(text))


def normalize_reference(reference: str) -> str:
    """Uppercase and remove punctuation/whitespace for stable comparisons."""
    return re.sub(r"[^A-Z0-9]", "", reference.upper())


def invoice_tokens(reference: str) -> list[str]:
    """Extract deduplicated six-digit invoice references after normalization."""
    tokens = re.findall(r"INV(\d{6})(?!\d)", normalize_reference(reference))
    return list(dict.fromkeys(f"INV-{token}" for token in tokens))


@dataclass(frozen=True)
class InvoiceCandidate:
    """Minimum evidence required by the exact-match rule."""

    invoice_number: str
    outstanding_cents: int


@dataclass(frozen=True)
class LineSnapshot:
    """Minimum evidence required to associate a reversal with its original."""

    id: str
    value_date: date
    amount_cents: int
    payer_name: str
    raw_reference: str


def exact_match(reference: str, amount_cents: int, invoices: list[InvoiceCandidate]) -> str | None:
    """Match one referenced open invoice for its entire balance; otherwise abstain."""
    if amount_cents <= 0 or has_injection(reference):
        return None
    tokens = invoice_tokens(reference)
    if len(tokens) != 1:
        return None
    candidates = [i for i in invoices if i.invoice_number == tokens[0] and i.outstanding_cents > 0]
    if len(candidates) != 1 or candidates[0].outstanding_cents != amount_cents:
        return None
    return candidates[0].invoice_number


def reversal_match(line: LineSnapshot, previous: list[LineSnapshot]) -> str | None:
    """Associate a negative line only with a unique equal prior payment within ten days."""
    if line.amount_cents >= 0:
        return None
    candidates = [
        p
        for p in previous
        if p.amount_cents == -line.amount_cents
        and normalize_reference(p.payer_name) == normalize_reference(line.payer_name)
        and normalize_reference(p.raw_reference) == normalize_reference(line.raw_reference)
        and 0 <= (line.value_date - p.value_date).days <= 10
    ]
    return candidates[0].id if len(candidates) == 1 else None
