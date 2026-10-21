"""Fail-closed accounting for sequential, explicitly priced live evaluation requests."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.app.agent.llm.base import LLMClient, ModelReply


class BudgetExceeded(RuntimeError):
    """No further provider requests are authorized by the evaluation budget."""


@dataclass
class EvaluationBudget:
    """Reserve a worst-case request before spending; reconcile with observed usage."""

    limit_usd: Decimal
    max_request_usd: Decimal
    max_requests: int = 4000
    spent_usd: Decimal = Decimal(0)
    measured_usd: Decimal = Decimal(0)
    requests: int = 0
    stopped: bool = False
    failure_type: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.limit_usd.is_finite()
            or not self.max_request_usd.is_finite()
            or not 0 < self.max_request_usd <= self.limit_usd
            or self.max_requests < 1
        ):
            raise ValueError("A finite positive budget and request bound are required")

    def reserve(self) -> None:
        """Count attempts, including failures whose final charge may be unknown."""
        if (
            self.stopped
            or self.requests >= self.max_requests
            or self.spent_usd + self.max_request_usd > self.limit_usd
        ):
            self.stopped = True
            self.failure_type = "BudgetExceeded"
            raise BudgetExceeded("Evaluation request or spending limit reached")
        self.requests += 1
        self.spent_usd += self.max_request_usd

    def reconcile(self, cost: Decimal | None) -> None:
        """Missing/invalid billing stops the run and retains the conservative reservation."""
        if cost is None or not cost.is_finite() or cost < 0:
            self.stopped = True
            self.failure_type = "InvalidMetering"
            raise BudgetExceeded("Provider usage did not satisfy the request cost bound")
        self.spent_usd += cost - self.max_request_usd
        self.measured_usd += cost
        if cost > self.max_request_usd:
            self.stopped = True
            self.failure_type = "ProviderExceededCostBound"
            raise BudgetExceeded("Provider exceeded its declared request cost bound")


class BudgetedClient:
    """Use only with a provider enforcing the configured price and output-token caps."""

    def __init__(self, client: LLMClient, budget: EvaluationBudget) -> None:
        self.client, self.budget, self.model = client, budget, client.model

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        """A failed or unmetered request retains its maximum possible charge."""
        self.budget.reserve()
        try:
            reply = await self.client.complete(messages, schemas, timeout)
        except BaseException as exc:
            self.budget.stopped = True
            self.budget.failure_type = type(exc).__name__
            raise
        self.budget.reconcile(reply.cost_usd)
        return reply

    async def aclose(self) -> None:
        """Release the provider transport without discarding the shared accounting ledger."""
        await self.client.aclose()
