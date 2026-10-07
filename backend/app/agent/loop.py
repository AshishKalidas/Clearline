"""A bounded, auditable tool loop that never directly writes an allocation."""

import asyncio
import json
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.agent.llm.base import LLMClient
from backend.app.agent.prompts import SYSTEM_PROMPT
from backend.app.agent.schemas import TOOL_MODELS, ProposalInput, tool_schemas
from backend.app.agent.service import route_proposal
from backend.app.agent.tools import ToolExecutor
from backend.app.agent.validation import validate_proposal
from backend.app.audit.service import record_event
from backend.app.config import Settings
from backend.app.db.models import BankLine, Proposal
from backend.app.matching.rules import has_injection


async def investigate(
    session: Session,
    line: BankLine,
    client: LLMClient,
    settings: Settings,
    *,
    max_steps: int = 8,
    max_seconds: float = 60.0,
) -> Proposal:
    """Execute validated read tools, then persist one terminal proposal or safe fallback."""
    start = time.monotonic()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "bank_line_id": line.id,
                    "amount_cents": line.amount_cents,
                    "value_date": str(line.value_date),
                    "untrusted_bank_text": {
                        "raw_reference": line.raw_reference,
                        "payer_name": line.payer_name,
                    },
                }
            ),
        },
    ]
    executor = ToolExecutor(session, line)
    steps = prompt_tokens = completion_tokens = failures = 0
    successful: set[str] = set()
    event_ids: list[str] = []
    value: ProposalInput | None = None
    fallback_flag = "agent_limit_reached"
    while steps < max_steps and value is None:
        remaining = max_seconds - (time.monotonic() - start)
        if remaining <= 0:
            break
        try:
            response = await asyncio.wait_for(
                client.complete(messages, tool_schemas(), remaining), remaining
            )
        except TimeoutError:
            break
        except Exception:
            fallback_flag = "provider_error"
            record_event(
                session,
                "provider_error",
                {"error": "provider request failed"},
                bank_line_id=line.id,
                actor="agent",
            )
            break
        prompt_tokens += response.prompt_tokens
        completion_tokens += response.completion_tokens
        if not response.calls:
            fallback_flag = "missing_terminal_proposal"
            break
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in response.calls
                ],
            }
        )
        for call in response.calls:
            if steps >= max_steps or time.monotonic() - start >= max_seconds:
                break
            steps += 1
            citation = f"{call.name}#{steps}"
            result: Any
            try:
                model = TOOL_MODELS.get(call.name)
                if model is None:
                    raise ValueError("unknown tool")
                args = model.model_validate(call.arguments)
                if isinstance(args, ProposalInput):
                    validate_proposal(session, line, args)
                    if args.allocations and (
                        not args.evidence or not set(args.evidence).issubset(successful)
                    ):
                        raise ValueError("allocations require citations to successful tools")
                    value = args
                    result = {"accepted": True}
                else:
                    result = executor.execute(call.name, args)
                    if not (isinstance(result, dict) and "error" in result):
                        successful.add(citation)
            except (ValidationError, ValueError) as exc:
                result = {
                    "error": "invalid_tool_arguments",
                    "detail": str(exc)
                    if isinstance(exc, ValueError) and not isinstance(exc, ValidationError)
                    else "Arguments do not match the tool schema",
                }
                if call.name == "submit_proposal":
                    failures += 1
            event = record_event(
                session,
                "tool_call",
                {
                    "step": steps,
                    "citation": citation,
                    "tool": call.name,
                    "arguments": call.arguments,
                    "result": result,
                },
                bank_line_id=line.id,
                actor="agent",
            )
            event_ids.append(event.id)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(result, default=str),
                }
            )
            if value is not None or failures >= 2:
                break
        if failures >= 2:
            fallback_flag = "proposal_validation_failed"
            break
    if value is None:
        value = ProposalInput(
            decision="escalate",
            confidence=0,
            reasoning="Investigation could not finish safely. Human review required.",
            risk_flags=[fallback_flag],
        )
    if has_injection(line.raw_reference) and "prompt_injection" not in value.risk_flags:
        value.risk_flags.append("prompt_injection")
    proposal = Proposal(
        bank_line_id=line.id,
        decision=value.decision,
        allocations_json=[a.model_dump() for a in value.allocations],
        confidence=value.confidence,
        reasoning=value.reasoning,
        evidence_json=value.evidence,
        risk_flags=value.risk_flags,
        model=client.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=int((time.monotonic() - start) * 1000),
        steps=steps,
    )
    session.add(proposal)
    session.flush()
    # Separate link events preserve audit append-only semantics.
    record_event(
        session,
        "proposal_submitted",
        {"proposal": value.model_dump(mode="json"), "tool_event_ids": event_ids},
        bank_line_id=line.id,
        proposal_id=proposal.id,
        actor="agent",
    )
    route_proposal(session, proposal, line, settings)
    return proposal
