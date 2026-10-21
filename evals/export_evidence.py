"""Publish validated evaluation snapshots for the offline-capable evidence page."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from evals.gates import release_gates

Provider = Literal["stub", "claude", "mimo"]


class Counts(BaseModel):
    """Keep denominators explicit and reject impossible population counts."""

    model_config = ConfigDict(strict=True)
    bank_cases: int = Field(ge=1)
    agent_cases: int = Field(ge=0)
    rules_matches: int = Field(ge=0)
    reversals: int = Field(ge=0)
    auto_applied: int = Field(ge=0)
    wrong_auto_applied: int = Field(ge=0)
    pop_cases: int = Field(ge=1)
    outbound_requests: int = Field(ge=0)

    @model_validator(mode="after")
    def coherent(self) -> "Counts":
        """Automatic decisions must be a subset of the evaluated agent cases."""
        if (
            not 0
            <= self.wrong_auto_applied
            <= self.auto_applied
            <= self.agent_cases
            <= self.bank_cases
        ):
            raise ValueError("evaluation counts are inconsistent")
        return self


class Scenario(BaseModel):
    """Expose measured successes with their own denominator."""

    model_config = ConfigDict(strict=True)
    correct: int = Field(ge=0)
    total: int = Field(gt=0)

    @model_validator(mode="after")
    def coherent(self) -> "Scenario":
        """A scenario cannot contain more successes than cases."""
        if self.correct > self.total:
            raise ValueError("scenario counts are inconsistent")
        return self


class Report(BaseModel):
    """Only measured, finite report fields may reach the public snapshot."""

    model_config = ConfigDict(allow_inf_nan=False, strict=True)
    provider: Provider
    model: str = Field(min_length=1)
    baseline: bool
    retrieval_enabled: bool
    embedder: Literal["hash", "local"]
    database: str = Field(min_length=1)
    created_at: AwareDatetime
    seed: int
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    counts: Counts
    metrics: dict[str, float | None]
    scenarios: dict[str, Scenario]
    gates: dict[str, bool]
    passed: bool
    invariant_errors: list[str]
    failure_count: int = Field(ge=0)

    @model_validator(mode="after")
    def truthful(self) -> "Report":
        """Recompute release gates; a hand-edited pass flag is not sufficient evidence."""
        if self.baseline != (self.provider == "stub"):
            raise ValueError("provider and baseline flag disagree")
        if sum(score.total for score in self.scenarios.values()) != self.counts.agent_cases:
            raise ValueError("scenario denominators disagree with agent case count")
        ratios = {
            "rules_match_rate": self.counts.rules_matches / self.counts.bank_cases,
            "false_allocation_rate": (
                self.counts.wrong_auto_applied / self.counts.auto_applied
                if self.counts.auto_applied
                else 0
            ),
            "agent_decision_accuracy": (
                sum(score.correct for score in self.scenarios.values()) / self.counts.agent_cases
                if self.counts.agent_cases
                else 0
            ),
        }
        for key, expected in ratios.items():
            observed = self.metrics.get(key)
            if observed is None or not math.isclose(observed, expected, abs_tol=1e-12):
                raise ValueError("measured ratios disagree with their denominators")
        for key in (
            "rules_precision",
            "false_allocation_rate",
            "escalation_recall",
            "injection_resistance",
            "pop_verdict_accuracy",
            "forged_pop_recall",
            "incomplete_investigations",
        ):
            if self.metrics.get(key) is None:
                raise ValueError("release evidence is missing a required measurement")
        if self.gates != release_gates(self.metrics, self.provider, self.invariant_errors):
            raise ValueError("recorded gates disagree with measured results")
        if self.passed != all(self.gates.values()):
            raise ValueError("overall pass flag disagrees with release gates")
        return self


def evidence_snapshot(reports: Path) -> str:
    """Build a deterministic six-slot snapshot; absent live runs remain null."""
    runs = []
    for provider in ("stub", "claude", "mimo"):
        for retrieval in (True, False):
            path = reports / f"{provider}-{'on' if retrieval else 'off'}/report.json"
            report = None
            digest = None
            if path.exists():
                raw = path.read_bytes()
                parsed = Report.model_validate_json(raw)
                if parsed.provider != provider or parsed.retrieval_enabled != retrieval:
                    raise ValueError(f"report identity does not match its directory: {path}")
                report = parsed.model_dump(mode="json")
                digest = hashlib.sha256(raw).hexdigest()
            runs.append(
                {
                    "provider": provider,
                    "retrieval_enabled": retrieval,
                    "report": report,
                    "report_sha256": digest,
                }
            )
    return json.dumps({"schema_version": 1, "runs": runs}, indent=2, allow_nan=False) + "\n"


def main() -> None:
    """Write the snapshot or verify that the checked-in asset is current."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("evals/reports"))
    parser.add_argument("--output", type=Path, default=Path("web/src/generated/evidence.json"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    snapshot = evidence_snapshot(args.reports)
    if args.check:
        if not args.output.exists() or args.output.read_text() != snapshot:
            raise SystemExit(
                "Evidence snapshot is stale. Run make evidence, then rebuild the web app."
            )
    elif args.stdout:
        print(snapshot, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(snapshot)


if __name__ == "__main__":
    main()
