import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI

from backend.app.agent.llm.base import ModelReply
from backend.app.agent.llm.openai_compat import OpenAICompatLLM
from backend.app.config import Settings
from evals.budget import BudgetedClient, BudgetExceeded, EvaluationBudget
from evals.live_run import Route, run_live
from evals.run_eval import evaluate


class MeteredFixture:
    model = "offline-metered-fixture"

    def __init__(self, cost: Decimal | None) -> None:
        self.cost = cost
        self.calls = 0

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        self.calls += 1
        return ModelReply(cost_usd=self.cost)

    async def aclose(self) -> None:
        return None


def test_worst_case_reservation_prevents_the_next_paid_request() -> None:
    provider = MeteredFixture(Decimal("0.15"))
    budget = EvaluationBudget(Decimal("0.30"), Decimal("0.20"))
    client = BudgetedClient(provider, budget)

    async def run() -> None:
        await client.complete([], [], 1)
        assert budget.spent_usd == Decimal("0.15")
        with pytest.raises(BudgetExceeded):
            await client.complete([], [], 1)

    asyncio.run(run())
    assert provider.calls == 1
    assert budget.stopped
    assert budget.spent_usd <= budget.limit_usd


@pytest.mark.parametrize(
    ("cost", "accounted"),
    [
        (None, Decimal("0.20")),
        (Decimal("NaN"), Decimal("0.20")),
        (Decimal("-1"), Decimal("0.20")),
        (Decimal("0.21"), Decimal("0.21")),
    ],
)
def test_untrustworthy_billing_blocks_further_requests_and_retains_reservation(
    cost: Decimal | None,
    accounted: Decimal,
) -> None:
    provider = MeteredFixture(cost)
    budget = EvaluationBudget(Decimal("1"), Decimal("0.20"))
    client = BudgetedClient(provider, budget)

    async def run() -> None:
        for _ in range(2):
            with pytest.raises(BudgetExceeded):
                await client.complete([], [], 1)

    asyncio.run(run())
    assert provider.calls == 1
    assert budget.spent_usd == accounted


def test_request_limit_applies_even_when_provider_billing_is_zero() -> None:
    provider = MeteredFixture(Decimal(0))
    budget = EvaluationBudget(Decimal("1"), Decimal("0.20"), max_requests=1)
    client = BudgetedClient(provider, budget)

    async def run() -> None:
        await client.complete([], [], 1)
        with pytest.raises(BudgetExceeded):
            await client.complete([], [], 1)

    asyncio.run(run())
    assert provider.calls == 1


def test_transport_cancellation_retains_the_reservation_without_retrying() -> None:
    class CancelledFixture(MeteredFixture):
        async def complete(
            self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
        ) -> ModelReply:
            self.calls += 1
            raise asyncio.CancelledError()

    provider = CancelledFixture(None)
    budget = EvaluationBudget(Decimal("1"), Decimal("0.20"))
    client = BudgetedClient(provider, budget)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(client.complete([], [], 1))
    assert budget.stopped and budget.failure_type == "CancelledError"
    assert budget.spent_usd == Decimal("0.20")
    with pytest.raises(BudgetExceeded):
        asyncio.run(client.complete([], [], 1))
    assert provider.calls == 1


def test_real_sdk_preserves_observed_cost_and_enforces_provider_and_token_caps() -> None:
    route = Route("Fixture Provider", 100000, Decimal("0.000001"), Decimal("0.000002"), Decimal(0))
    fixture = json.loads(Path("backend/tests/fixtures/mimo_tool_response.json").read_text())
    fixture["usage"]["cost"] = 0.00019

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["max_tokens"] == 2048
        assert body["provider"]["only"] == ["Fixture Provider"]
        assert body["provider"]["max_price"] == {"prompt": 1, "completion": 2, "request": 0}
        assert body["reasoning"] == {"enabled": False}
        return httpx.Response(200, json=fixture)

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        sdk = AsyncOpenAI(api_key="offline-fixture", http_client=http, max_retries=0)
        client = OpenAICompatLLM(
            Settings(mimo_model="fixture-model"), sdk=sdk, provider_options=route.options()
        )
        try:
            reply = await client.complete([], [], 5)
            assert reply.cost_usd == Decimal("0.00019")
        finally:
            await client.aclose()

    asyncio.run(run())


def test_pilot_samples_every_agent_scenario_and_declares_its_partial_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    report = asyncio.run(evaluate("stub", True, tmp_path, max_agent_cases=20))
    assert report["evaluation_scope"] == "pilot"
    assert report["eligible_agent_cases"] == 228
    assert report["counts"]["agent_cases"] == 20
    assert len(report["scenarios"]) == 10
    assert all(score["total"] == 2 for score in report["scenarios"].values())
    assert report["passed"]


def test_single_mode_run_preserves_separate_execution_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested: list[bool] = []
    settings = Settings(
        mimo_base_url="https://openrouter.ai/api/v1",
        mimo_api_key="offline-fixture",
        mimo_model="xiaomi/mimo-fixture",
    )
    monkeypatch.setattr("evals.live_run.get_settings", lambda: settings)
    monkeypatch.setattr(
        "evals.live_run.load_route",
        lambda *_: Route("Fixture", 1000, Decimal("0.000001"), Decimal("0.000002"), Decimal(0)),
    )

    async def fake_evaluate(
        provider: str, retrieval: bool, out: Path, **kwargs: Any
    ) -> dict[str, Any]:
        requested.append(retrieval)
        (out / "mimo-off").mkdir()
        return {"passed": False}

    monkeypatch.setattr("evals.live_run.evaluate", fake_evaluate)
    monkeypatch.setattr("evals.live_run.refresh_lift", lambda *_: None)
    monkeypatch.setattr("evals.live_run.regenerate_markdown", lambda *_: None)
    summary = asyncio.run(run_live(out=tmp_path, limit_usd=Decimal("1"), retrieval_modes=(False,)))
    assert requested == [False]
    assert summary["completed_modes"] == {"off": False}
    assert not (tmp_path / "mimo-on").exists()
    report = json.loads((tmp_path / "mimo-off/report.json").read_text())
    assert report["evaluation_id"] == summary["evaluation_id"]
    receipt = (tmp_path / "execution.json").read_bytes()
    with pytest.raises(ValueError, match="fresh output directory"):
        asyncio.run(run_live(out=tmp_path, limit_usd=Decimal("1"), retrieval_modes=(False,)))
    assert (tmp_path / "execution.json").read_bytes() == receipt
    assert requested == [False]


def test_existing_mode_report_blocks_requests_even_without_an_execution_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        mimo_base_url="https://openrouter.ai/api/v1",
        mimo_api_key="offline-fixture",
        mimo_model="xiaomi/mimo-fixture",
    )
    monkeypatch.setattr("evals.live_run.get_settings", lambda: settings)

    def unexpected_catalog_request(*args: Any) -> None:
        pytest.fail("Existing evidence must be rejected before any provider request")

    monkeypatch.setattr("evals.live_run.load_route", unexpected_catalog_request)
    report = tmp_path / "mimo-off/report.json"
    report.parent.mkdir()
    report.write_text("existing evidence")
    with pytest.raises(ValueError, match="fresh output directory"):
        asyncio.run(run_live(out=tmp_path, limit_usd=Decimal("1"), retrieval_modes=(False,)))
    assert report.read_text() == "existing evidence"
