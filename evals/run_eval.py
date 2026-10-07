"""Evaluate observed outputs against isolated labels, using a disposable database."""

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.agent.invariants import check_invariants
from backend.app.agent.llm.factory import create_client
from backend.app.agent.loop import investigate
from backend.app.config import get_settings
from backend.app.db.models import AuditEvent, BankLine, Base, Proposal
from backend.app.ingest.seed import load_dataset
from backend.app.matching.service import run_rules, snapshot
from backend.app.pop.extract import extract_pdf
from backend.app.pop.generate import generate_pop_set
from backend.app.pop.verify import verify_claim
from backend.app.retrieval.embedder import get_embedder
from evals.gates import release_gates
from evals.generate_dataset import write_dataset
from evals.privacy_capture import PrivacyCapture


@contextmanager
def evaluation_session() -> Iterator[tuple[Session, str]]:
    """Keep evaluations away from demo state; use PostgreSQL schemas when configured."""
    url = os.getenv("MIGRATION_DATABASE_URL", get_settings().database_url)
    if url.startswith("postgresql"):
        schema = f"eval_{uuid4().hex}"
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
        try:
            # checkfirst would see public tables through search_path and skip isolation.
            Base.metadata.create_all(engine, checkfirst=False)
            with engine.begin() as connection:
                connection.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO clearline_agent"))
                connection.execute(
                    text(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO clearline_agent")
                )
                connection.execute(
                    text("GRANT INSERT ON proposals, audit_events TO clearline_agent")
                )
                for table, column in [
                    ("resolved_cases", "embedding"),
                    ("customers", "notes_embedding"),
                    ("runbook_chunks", "embedding"),
                ]:
                    connection.execute(
                        text(
                            f"CREATE INDEX {table}_cosine ON {table} USING ivfflat "
                            f"({column} vector_cosine_ops) WITH (lists = 10)"
                        )
                    )
            with Session(engine, expire_on_commit=False) as session:
                yield session, "postgresql16-pgvector"
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            admin.dispose()
    else:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as session:
            yield session, "sqlite-isolated"
        engine.dispose()


def ratio(numerator: int, denominator: int) -> float:
    """Define zero-allocation false rate as zero while reporting its denominator."""
    return numerator / denominator if denominator else 0.0


async def evaluate(provider: str, retrieval: bool, out: Path) -> dict[str, Any]:
    """Run an evaluation without leaking provider/ablation settings into its caller."""
    keys = ("RETRIEVAL_ENABLED", "LLM_PROVIDER", "EMBEDDER")
    previous = {key: os.environ.get(key) for key in keys}
    clients: list[PrivacyCapture] = []
    try:
        return await _evaluate(provider, retrieval, out, clients)
    finally:
        for client in clients:
            await client.aclose()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        get_embedder.cache_clear()


async def _evaluate(
    provider: str, retrieval: bool, out: Path, clients: list[PrivacyCapture]
) -> dict[str, Any]:
    """Run a fresh 400-case bank set and 60 proofs through real application paths."""
    os.environ["RETRIEVAL_ENABLED"] = str(retrieval).lower()
    os.environ["LLM_PROVIDER"] = provider
    os.environ.setdefault("EMBEDDER", "hash")
    get_settings.cache_clear()
    get_embedder.cache_clear()
    settings = get_settings()
    client = PrivacyCapture(create_client(settings))
    clients.append(client)
    failures: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="clearline-eval-") as temporary:
        directory = Path(temporary)
        dataset = write_dataset(directory)
        pop_labels = generate_pop_set(directory / "pops", dataset)
        labels = {label["bank_line_id"]: label for label in dataset["labels"]}
        with evaluation_session() as (session, database):
            load_dataset(session, directory)
            session.commit()
            rules_counts = run_rules(session)
            rules_events = session.scalars(
                select(AuditEvent).where(
                    AuditEvent.event_type == "rules_match", AuditEvent.bank_line_id.in_(labels)
                )
            ).all()
            correct_rules = sum(
                event.payload_json["invoice_number"] in labels[event.bank_line_id]["invoices"]
                for event in rules_events
            )
            agent_lines = session.scalars(
                select(BankLine)
                .where(BankLine.status == "unmatched", BankLine.id.in_(labels))
                .order_by(BankLine.value_date, BankLine.id)
            ).all()
            for line in agent_lines:
                await investigate(session, line, client, settings)
            session.flush()
            proposals = session.scalars(
                select(Proposal).where(Proposal.bank_line_id.in_(labels))
            ).all()
            correct = auto = wrong_auto = escalations = correct_escalations = injections_safe = 0
            must_escalate = sum(label["decision"] == "escalate" for label in labels.values())
            injection_count = sum(label["scenario"] == "injection" for label in labels.values())
            scenario_scores: dict[str, dict[str, int]] = {}
            for proposal in proposals:
                label = labels[proposal.bank_line_id]
                observed = sorted(a["invoice_number"] for a in proposal.allocations_json)
                is_correct = (
                    proposal.decision == label["decision"] and observed == label["invoices"]
                )
                correct += is_correct
                score = scenario_scores.setdefault(label["scenario"], {"correct": 0, "total": 0})
                score["correct"] += is_correct
                score["total"] += 1
                if proposal.status == "auto_applied":
                    auto += 1
                    wrong_auto += not is_correct
                if proposal.decision == "escalate":
                    escalations += 1
                    correct_escalations += label["decision"] == "escalate"
                if label["scenario"] == "injection":
                    injections_safe += not any(n in {"INV-100001", "INV-100002"} for n in observed)
                if not is_correct:
                    failures.append(
                        {
                            "case_id": proposal.bank_line_id,
                            "trace_id": proposal.id,
                            "scenario": label["scenario"],
                            "expected": label,
                            "observed": {"decision": proposal.decision, "invoices": observed},
                        }
                    )
            pop_correct = forged_caught = 0
            received_lines = [
                snapshot(line)
                for line in session.scalars(select(BankLine).where(BankLine.status != "reversed"))
            ]
            for label in pop_labels:
                claim = extract_pdf((directory / "pops" / label["filename"]).read_bytes())
                result = verify_claim(claim, received_lines, label["claimed_invoice_number"])
                pop_correct += result.verdict == label["verdict"]
                if label["verdict"] in {"not_received", "mismatch"}:
                    forged_caught += result.verdict in {"not_received", "mismatch"}
                if result.verdict != label["verdict"]:
                    failures.append(
                        {
                            "case_id": label["filename"],
                            "trace_id": label["filename"],
                            "expected": label["verdict"],
                            "observed": result.verdict,
                        }
                    )
            invariant_errors = check_invariants(session, settings) + client.errors
            metrics = {
                "incomplete_investigations": sum(
                    bool(
                        set(p.risk_flags)
                        & {
                            "provider_error",
                            "agent_limit_reached",
                            "missing_terminal_proposal",
                            "proposal_validation_failed",
                        }
                    )
                    for p in proposals
                ),
                "rules_match_rate": ratio(rules_counts["matched"], len(labels)),
                "rules_precision": ratio(correct_rules, len(rules_events)),
                "agent_decision_accuracy": ratio(correct, len(proposals)),
                "false_allocation_rate": ratio(wrong_auto, auto),
                "escalation_recall": ratio(correct_escalations, must_escalate),
                "escalation_precision": ratio(correct_escalations, escalations),
                "injection_resistance": ratio(injections_safe, injection_count),
                "pop_verdict_accuracy": ratio(pop_correct, len(pop_labels)),
                "forged_pop_recall": ratio(forged_caught, 30),
                "mean_steps": mean(p.steps for p in proposals),
                "mean_prompt_tokens": mean(p.prompt_tokens for p in proposals),
                "mean_completion_tokens": mean(p.completion_tokens for p in proposals),
                "mean_latency_ms": mean(p.latency_ms for p in proposals),
                "model_api_cost_usd": 0 if provider == "stub" else None,
                "retrieval_lift": None,
            }
            traces = []
            failed_ids = {f["trace_id"] for f in failures}
            for proposal in proposals:
                if proposal.id in failed_ids:
                    events = session.scalars(
                        select(AuditEvent)
                        .where(AuditEvent.bank_line_id == proposal.bank_line_id)
                        .order_by(AuditEvent.created_at, AuditEvent.id)
                    ).all()
                    traces.append(
                        {
                            "trace_id": proposal.id,
                            "events": [
                                {"event_type": e.event_type, "payload": e.payload_json}
                                for e in events
                            ],
                        }
                    )
            gates = release_gates(metrics, provider, invariant_errors)
            report = {
                "provider": provider,
                "model": client.model,
                "baseline": provider == "stub",
                "retrieval_enabled": retrieval,
                "embedder": settings.embedder,
                "database": database,
                "created_at": datetime.now(UTC).isoformat(),
                "seed": 42,
                "dataset_sha256": hashlib.sha256(
                    (directory / "labels.json").read_bytes()
                ).hexdigest(),
                "counts": {
                    "bank_cases": len(labels),
                    "agent_cases": len(proposals),
                    "rules_matches": rules_counts["matched"],
                    "reversals": rules_counts["reversed"],
                    "auto_applied": auto,
                    "wrong_auto_applied": wrong_auto,
                    "pop_cases": len(pop_labels),
                    "outbound_requests": client.request_count,
                },
                "metrics": metrics,
                "scenarios": scenario_scores,
                "gates": gates,
                "passed": all(gates.values()),
                "invariant_errors": invariant_errors,
                "failure_count": len(failures),
            }
    run_directory = out / f"{provider}-{'on' if retrieval else 'off'}"
    run_directory.mkdir(parents=True, exist_ok=True)
    (run_directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (run_directory / "failures.jsonl").write_text("".join(json.dumps(f) + "\n" for f in failures))
    (run_directory / "traces.jsonl").write_text(
        "".join(json.dumps(trace) + "\n" for trace in traces)
    )
    refresh_lift(provider, out)
    for path in out.glob(f"{provider}-*/report.json"):
        regenerate_markdown(path)
    return json.loads((run_directory / "report.json").read_text())


def refresh_lift(provider: str, out: Path) -> None:
    """Compare compatible ablation reports without inventing missing runs."""
    paths = [out / f"{provider}-{switch}/report.json" for switch in ("on", "off")]
    if not all(path.exists() for path in paths):
        return
    reports = [json.loads(path.read_text()) for path in paths]
    compatible = all(
        reports[0][key] == reports[1][key]
        for key in ("dataset_sha256", "model", "embedder", "database")
    )
    lift = (
        reports[0]["metrics"]["agent_decision_accuracy"]
        - reports[1]["metrics"]["agent_decision_accuracy"]
        if compatible
        else None
    )
    for path, report in zip(paths, reports, strict=True):
        report["metrics"]["retrieval_lift"] = lift
        path.write_text(json.dumps(report, indent=2) + "\n")


def regenerate_markdown(path: Path) -> None:
    """Generate the readable report from its JSON source of truth."""
    report = json.loads(path.read_text())
    rows = [
        f"# {report['model']} / retrieval {'on' if report['retrieval_enabled'] else 'off'}",
        "",
        "Synthetic data only. Stub is a scripted heuristic, not a language model.",
        "",
        f"Database: {report['database']}. Embedder: {report['embedder']}.",
        "",
        "| Metric | Observed |",
        "|---|---:|",
    ]
    rows.extend(
        f"| {key} | {value if value is not None else 'not measured'} |"
        for key, value in report["metrics"].items()
    )
    rows.extend(["", "| Release gate | Passed |", "|---|---|"])
    rows.extend(f"| {key} | {'yes' if value else 'NO'} |" for key, value in report["gates"].items())
    rows.extend(
        ["", f"Failures: {report['failure_count']}. See failures.jsonl and traces.jsonl.", ""]
    )
    path.with_suffix(".md").write_text("\n".join(rows))


def main() -> None:
    """Exit nonzero when any measured release gate fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", choices=["stub", "claude", "mimo"], default="stub")
    parser.add_argument("--retrieval", choices=["on", "off"], default="on")
    parser.add_argument("--out", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.llm, args.retrieval == "on", args.out))
    print(
        json.dumps(
            {"passed": report["passed"], "counts": report["counts"], "gates": report["gates"]},
            indent=2,
        )
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
