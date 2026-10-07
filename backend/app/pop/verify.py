"""Pure bank-evidence verification. PDF appearance contributes no trust."""

from dataclasses import dataclass
from typing import Any, Literal

from backend.app.matching.rules import LineSnapshot, normalize_reference
from backend.app.pop.extract import PaymentClaim
from backend.app.pop.generate import money

Verdict = Literal["verified", "not_received", "mismatch", "unreadable"]


@dataclass(frozen=True)
class Verification:
    """Verdict, linked evidence and individual checks."""

    verdict: Verdict
    matched_bank_line_id: str | None
    checks: list[dict[str, Any]]
    summary: str


def verify_claim(
    claim: PaymentClaim | None,
    lines: list[LineSnapshot],
    claimed_invoice_number: str | None = None,
    beneficiary_last4: str = "0042",
) -> Verification:
    """Check received positive bank observations and explain each inconsistency."""
    if claim is None:
        return Verification(
            "unreadable",
            None,
            [{"check": "required_fields", "passed": False}],
            "This document is unreadable or has missing fields. Do not release goods.",
        )
    related = [
        line
        for line in lines
        if line.amount_cents > 0
        and (
            normalize_reference(line.payer_name) == normalize_reference(claim.payer_name)
            or normalize_reference(line.raw_reference) == normalize_reference(claim.reference)
        )
    ]
    if not related:
        return Verification(
            "not_received",
            None,
            [{"check": "bank_presence", "passed": False}],
            f"No payment of {money(claim.amount_cents)} from this payer has arrived. "
            "Do not release goods.",
        )

    def checks_for(line: LineSnapshot) -> list[dict[str, Any]]:
        return [
            {"check": "bank_presence", "passed": True},
            {
                "check": "amount",
                "passed": claim.amount_cents == line.amount_cents,
                "claimed": claim.amount_cents,
                "observed": line.amount_cents,
            },
            {
                "check": "date_within_two_days",
                "passed": abs((claim.payment_date - line.value_date).days) <= 2,
                "claimed": str(claim.payment_date),
                "observed": str(line.value_date),
            },
            {
                "check": "payer",
                "passed": normalize_reference(claim.payer_name)
                == normalize_reference(line.payer_name),
            },
            {
                "check": "reference",
                "passed": normalize_reference(claim.reference)
                == normalize_reference(line.raw_reference),
            },
            {"check": "beneficiary", "passed": claim.beneficiary_last4 == beneficiary_last4},
            {
                "check": "claimed_invoice",
                "passed": claimed_invoice_number is None
                or normalize_reference(claim.reference)
                == normalize_reference(claimed_invoice_number),
            },
        ]

    ranked = sorted(
        related,
        key=lambda line: (
            sum(not c["passed"] for c in checks_for(line)),
            abs((claim.payment_date - line.value_date).days),
            line.id,
        ),
    )
    line = ranked[0]
    checks = checks_for(line)
    if all(check["passed"] for check in checks):
        return Verification(
            "verified",
            line.id,
            checks,
            f"Bank evidence confirms {money(claim.amount_cents)} within the date tolerance. "
            "Review invoice settlement before dispatch.",
        )
    failed = ", ".join(c["check"] for c in checks if not c["passed"])
    return Verification(
        "mismatch",
        line.id,
        checks,
        f"The payment claim disagrees with bank evidence ({failed}). Do not release goods.",
    )
