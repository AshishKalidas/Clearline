"""Run explicitly budgeted MiMo evaluations through a price-capped OpenRouter route."""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from openai import AsyncOpenAI

from backend.app.agent.llm.base import LLMClient
from backend.app.agent.llm.openai_compat import OpenAICompatLLM
from backend.app.config import Settings, get_settings
from evals.budget import BudgetedClient, BudgetExceeded, EvaluationBudget
from evals.run_eval import evaluate, refresh_lift, regenerate_markdown

OPENROUTER_URL = "https://openrouter.ai/api/v1"
OUTPUT_TOKENS = 2048


@dataclass(frozen=True)
class Route:
    """Observed catalog prices and context bounds for one pinned upstream provider."""

    provider: str
    context_tokens: int
    prompt_price: Decimal
    completion_price: Decimal
    request_price: Decimal

    @property
    def max_request_usd(self) -> Decimal:
        """Reserve the whole model context, rather than estimating tokenizer behavior."""
        return (
            self.context_tokens * self.prompt_price
            + OUTPUT_TOKENS * self.completion_price
            + self.request_price
        )

    def options(self) -> dict[str, object]:
        """Enforce catalog price ceilings upstream and disable unbudgeted reasoning output."""
        return {
            "provider": {
                "only": [self.provider],
                "require_parameters": True,
                "max_price": {
                    "prompt": float(self.prompt_price * 1_000_000),
                    "completion": float(self.completion_price * 1_000_000),
                    "request": float(self.request_price),
                },
            },
            "reasoning": {"enabled": False},
        }


def load_route(model: str, provider: str) -> Route:
    """Read public endpoint metadata; do not send an API credential to this endpoint."""
    if not model.startswith("xiaomi/mimo-"):
        raise ValueError("The MiMo evaluation slot requires an explicit Xiaomi MiMo model")
    response = httpx.get(f"{OPENROUTER_URL}/models/{model}/endpoints", timeout=30)
    response.raise_for_status()
    endpoints = response.json()["data"]["endpoints"]
    endpoint = next((item for item in endpoints if item["provider_name"] == provider), None)
    if endpoint is None or not {"tools", "tool_choice", "max_tokens"}.issubset(
        endpoint["supported_parameters"]
    ):
        raise ValueError("The requested provider must support tools and output-token limits")
    prices = endpoint["pricing"]
    route = Route(
        provider,
        int(endpoint["context_length"]),
        Decimal(prices["prompt"]),
        Decimal(prices["completion"]),
        Decimal(prices.get("request", "0")),
    )
    if route.context_tokens < 1 or any(
        not price.is_finite() or price < 0
        for price in (route.prompt_price, route.completion_price, route.request_price)
    ):
        raise ValueError("Provider catalog returned invalid price or context bounds")
    return route


async def run_live(
    *,
    out: Path,
    limit_usd: Decimal,
    provider: str = "Xiaomi",
    max_agent_cases: int | None = None,
    retrieval_modes: tuple[bool, ...] = (True, False),
) -> dict[str, Any]:
    """Share one cost ledger across retrieval modes; never change the running demo's settings."""
    settings = get_settings()
    if settings.mimo_base_url.rstrip("/") != OPENROUTER_URL or not settings.mimo_api_key:
        raise ValueError("Configure the OpenRouter URL and key in the MiMo provider settings")
    if max_agent_cases is not None and out.resolve() == Path("evals/reports").resolve():
        raise ValueError("Pilot runs must use a separate output directory")
    if not retrieval_modes or len(set(retrieval_modes)) != len(retrieval_modes):
        raise ValueError("Choose one or both distinct retrieval modes")
    if (out / "execution.json").exists() or any(
        (out / f"mimo-{'on' if mode else 'off'}/report.json").exists() for mode in retrieval_modes
    ):
        raise ValueError(
            "Choose a fresh output directory; existing execution evidence is preserved"
        )
    route = load_route(settings.mimo_model, provider)
    budget = EvaluationBudget(limit_usd, route.max_request_usd)
    out.mkdir(parents=True, exist_ok=True)
    completed: dict[str, bool] = {}
    execution_failure: str | None = None
    started = time.monotonic()
    execution_id = uuid4().hex

    def client_factory(config: Settings) -> LLMClient:
        # Retrying an uncertain request can incur another charge. Budgeted runs do not retry.
        sdk = AsyncOpenAI(
            api_key=config.mimo_api_key.get_secret_value(),
            base_url=OPENROUTER_URL,
            timeout=15,
            max_retries=0,
        )
        return BudgetedClient(
            OpenAICompatLLM(config, sdk=sdk, provider_options=route.options()), budget
        )

    def progress(done: int, total: int) -> None:
        print(
            json.dumps(
                {"completed": done, "total": total, "accounted_cost_usd": str(budget.spent_usd)}
            ),
            flush=True,
        )
        if budget.stopped:
            raise BudgetExceeded("Evaluation stopped after an uncertain or capped provider request")

    try:
        for retrieval in retrieval_modes:
            mode = "on" if retrieval else "off"
            report = await evaluate(
                "mimo",
                retrieval,
                out,
                max_agent_cases=max_agent_cases,
                client_factory=client_factory,
                progress=progress,
            )
            report["live_configuration"] = {
                "gateway": "OpenRouter",
                "upstream_provider": provider,
                "output_token_limit": OUTPUT_TOKENS,
                "temperature": 0,
                "reasoning_enabled": False,
                "sdk_retries": 0,
                "provider_options": route.options(),
            }
            report["evaluation_id"] = execution_id
            path = out / f"mimo-{mode}/report.json"
            path.write_text(json.dumps(report, indent=2) + "\n")
            regenerate_markdown(path)
            completed[mode] = report["passed"]
        refresh_lift("mimo", out)
        for retrieval in retrieval_modes:
            regenerate_markdown(out / f"mimo-{'on' if retrieval else 'off'}/report.json")
    except BaseException as exc:
        execution_failure = type(exc).__name__
        raise
    finally:
        summary = {
            "model": settings.mimo_model,
            "evaluation_id": execution_id,
            "gateway": "OpenRouter",
            "upstream_provider": provider,
            "evaluation_scope": "full" if max_agent_cases is None else "pilot",
            "spend_limit_usd": str(limit_usd),
            "accounted_cost_usd": str(budget.spent_usd),
            "measured_cost_usd": str(budget.measured_usd),
            "unsettled_reservation_usd": str(budget.spent_usd - budget.measured_usd),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "max_request_reservation_usd": str(route.max_request_usd),
            "request_attempts": budget.requests,
            "stopped": budget.stopped,
            "failure_type": budget.failure_type,
            "execution_failure_type": execution_failure,
            "completed_modes": completed,
        }
        (out / "execution.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    """Require an explicit dollar budget before making any model requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-usd", type=Decimal, required=True)
    parser.add_argument("--provider", default="Xiaomi")
    parser.add_argument("--max-agent-cases", type=int)
    parser.add_argument("--retrieval", choices=["both", "on", "off"], default="both")
    parser.add_argument("--out", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    summary = asyncio.run(
        run_live(
            out=args.out,
            limit_usd=args.budget_usd,
            provider=args.provider,
            max_agent_cases=args.max_agent_cases,
            retrieval_modes=(True, False)
            if args.retrieval == "both"
            else (args.retrieval == "on",),
        )
    )
    print(json.dumps(summary, indent=2))
    if not all(summary["completed_modes"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
