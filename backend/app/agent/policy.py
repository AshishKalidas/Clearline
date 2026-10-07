"""Deterministic policy: confidence alone never authorizes the ledger."""

from dataclasses import dataclass

from backend.app.config import Settings


@dataclass(frozen=True)
class PolicyFacts:
    """Independent facts required for automatic application."""

    decision: str
    confidence: float
    amount_cents: int
    risk_flags: list[str]
    pop_mismatch: bool
    has_customer_history: bool


def evaluate_policy(facts: PolicyFacts, settings: Settings) -> tuple[bool, str]:
    """Return authorization and all failed conditions for a reviewer to inspect."""
    failures = []
    if facts.decision != "match":
        failures.append("decision is not a full single-invoice match")
    if facts.confidence < settings.auto_confidence:
        failures.append("confidence below AUTO_CONFIDENCE")
    if facts.amount_cents > settings.auto_limit_cents or facts.amount_cents <= 0:
        failures.append("amount outside AUTO_LIMIT_CENTS")
    if facts.risk_flags:
        failures.append("risk flags require review")
    if facts.pop_mismatch:
        failures.append("linked proof of payment is mismatch")
    if not facts.has_customer_history:
        failures.append("customer has no prior resolved case")
    return not failures, "; ".join(failures) or "All automatic allocation conditions satisfied"
