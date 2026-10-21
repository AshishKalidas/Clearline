"""Observe the final normalized model boundary without persisting unmasked inputs."""

from decimal import Decimal
from typing import Any

from backend.app.agent.llm.base import LLMClient, ModelReply
from backend.app.privacy.masking import Masker


class PrivacyCapture:
    """Delegate requests and retain counts/violations, never the source PII mapping."""

    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.model = client.model
        self.request_count = 0
        self.errors: list[str] = []
        self.metered_requests = 0
        self.cost_usd = Decimal(0)

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        """Verify the final outgoing boundary and forward a defensively masked request."""
        self.request_count += 1
        cleaned = Masker().clean(messages)
        if cleaned != messages:
            self.errors.append(
                f"Outbound request {self.request_count} contained a sensitive pattern"
            )
        reply = await self.client.complete(cleaned, schemas, timeout)
        if reply.cost_usd is not None:
            self.metered_requests += 1
            self.cost_usd += reply.cost_usd
        return reply

    async def aclose(self) -> None:
        """Release the wrapped provider's transport."""
        await self.client.aclose()
