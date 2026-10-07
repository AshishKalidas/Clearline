"""Deterministic heuristic baseline, explicitly not a language model."""

import json
from typing import Any

from backend.app.agent.llm.base import ModelReply, ToolCall
from backend.app.matching.rules import has_injection


class StubLLM:
    """Exercise the real tools, validation, policy and trace without networking."""

    model = "stub-baseline-v1"

    async def complete(
        self,
        messages: list[dict[str, Any]],
        schemas: list[dict[str, object]],
        timeout: float,
    ) -> ModelReply:
        context = json.loads(messages[1]["content"])
        results: dict[str, Any] = {}
        for message in messages:
            if message["role"] == "tool":
                results[message["name"]] = json.loads(message["content"])
        text = context["untrusted_bank_text"]
        customers = results.get("find_customers", [])
        candidate = customers[0] if customers and customers[0]["score"] >= 0.95 else None
        if "find_customers" not in results:
            name, args = "find_customers", {"name_query": text["payer_name"]}
        elif "search_invoices" not in results:
            name, args = (
                "search_invoices",
                (
                    {"customer_id": candidate["id"]}
                    if candidate
                    else {"reference_like": "NO-CANDIDATE"}
                ),
            )
        elif "find_duplicate_candidates" not in results:
            name, args = "find_duplicate_candidates", {}
        elif "find_similar_cases" not in results:
            name, args = (
                "find_similar_cases",
                {"k": 5, "customer_id": candidate["id"] if candidate else None},
            )
        elif "search_runbook" not in results:
            name, args = (
                "search_runbook",
                {"query": "allocation shortfall overpayment split", "k": 3},
            )
        else:
            name, args = "submit_proposal", self.propose(context, results, candidate)
        return ModelReply([ToolCall(f"stub-{len(results) + 1}", name, args)])

    @staticmethod
    def propose(
        context: dict[str, Any],
        results: dict[str, Any],
        customer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Use conservative transparent heuristics on observed tool results only."""
        amount = context["amount_cents"]
        invoices = results.get("search_invoices", [])
        flags: list[str] = []
        allocations: list[dict[str, Any]] = []
        decision = "escalate"
        confidence = 0.5
        reason = "No unique, evidence-supported allocation. Human investigation required."
        if has_injection(context["untrusted_bank_text"]["raw_reference"]):
            flags = ["prompt_injection"]
            reason = "Instruction-like bank text is untrusted. Escalated without an allocation."
        elif amount <= 0:
            flags = ["unmatched_reversal"]
        elif results.get("find_duplicate_candidates"):
            decision, confidence = "duplicate", 0.98
            reason = "A prior settled bank line has the same payer and amount within seven days."
        elif customer is not None:
            exact = [i for i in invoices if i["outstanding_cents"] == amount]
            if len(exact) == 1:
                decision, confidence = "match", 0.96
                allocations = [
                    {"invoice_number": exact[0]["invoice_number"], "amount_cents": amount}
                ]
                reason = (
                    f"Payer identifies {customer['account_code']}; "
                    "one open invoice equals the bank amount."
                )
            elif len(exact) > 1:
                flags = ["ambiguous_candidates"]
                reason = "Two open invoices for this customer have equally plausible amounts."
            elif len(invoices) > 1 and sum(i["outstanding_cents"] for i in invoices) == amount:
                decision, confidence = "split", 0.92
                allocations = [
                    {"invoice_number": i["invoice_number"], "amount_cents": i["outstanding_cents"]}
                    for i in invoices
                ]
                reason = "Bank amount equals all candidate balances, ordered oldest invoice first."
            elif len(invoices) == 1:
                invoice = invoices[0]
                balance = invoice["outstanding_cents"]
                decision, confidence = ("partial" if amount < balance else "overpayment"), 0.93
                allocations = [
                    {
                        "invoice_number": invoice["invoice_number"],
                        "amount_cents": min(amount, balance),
                    }
                ]
                reason = (
                    "Unique customer invoice; apply received money up to its outstanding balance."
                )
            else:
                flags = ["insufficient_evidence"]
        else:
            flags = ["unknown_payer"]
        return {
            "decision": decision,
            "allocations": allocations,
            "confidence": confidence,
            "reasoning": reason,
            "evidence": ["find_customers#1", "search_invoices#2", "find_duplicate_candidates#3"],
            "risk_flags": flags,
        }
