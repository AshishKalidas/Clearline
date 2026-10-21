import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.export_evidence import evidence_snapshot
from evals.gates import release_gates

SOURCE = Path("evals/reports/stub-on/report.json")


def test_snapshot_preserves_provenance_and_leaves_missing_runs_unmeasured(tmp_path: Path) -> None:
    destination = tmp_path / "stub-on/report.json"
    destination.parent.mkdir()
    destination.write_bytes(SOURCE.read_bytes())
    first = evidence_snapshot(tmp_path)
    assert evidence_snapshot(tmp_path) == first
    runs = json.loads(first)["runs"]
    assert len(runs) == 6
    assert runs[0]["report_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert runs[0]["report"]["counts"]["auto_applied"] > 0
    assert runs[1]["report"] is None
    assert all(run["report"] is None for run in runs if run["provider"] != "stub")


@pytest.mark.parametrize(
    "mutation", ["gate", "counts", "identity", "nan", "baseline", "overall", "ratio", "missing"]
)
def test_export_rejects_contradictory_evidence(tmp_path: Path, mutation: str) -> None:
    report = json.loads(SOURCE.read_text())
    if mutation == "gate":
        report["metrics"]["false_allocation_rate"] = 0.2
    elif mutation == "counts":
        report["counts"]["wrong_auto_applied"] = 1000
    elif mutation == "identity":
        report["provider"] = "mimo"
        report["baseline"] = False
    elif mutation == "nan":
        report["metrics"]["mean_latency_ms"] = float("nan")
    elif mutation == "baseline":
        report["baseline"] = False
    elif mutation == "missing":
        del report["metrics"]["incomplete_investigations"]
    elif mutation == "ratio":
        report["scenarios"]["split"]["correct"] -= 1
    else:
        report["passed"] = False
    destination = tmp_path / "stub-on/report.json"
    destination.parent.mkdir()
    destination.write_text(json.dumps(report))
    with pytest.raises((ValidationError, ValueError)):
        evidence_snapshot(tmp_path)


def test_coherent_failed_run_is_published_without_hiding_its_failed_gate(tmp_path: Path) -> None:
    report = json.loads(SOURCE.read_text())
    report["counts"]["wrong_auto_applied"] = 1
    report["metrics"]["false_allocation_rate"] = 1 / report["counts"]["auto_applied"]
    report["scenarios"]["split"]["correct"] -= 1
    report["metrics"]["agent_decision_accuracy"] = (
        sum(score["correct"] for score in report["scenarios"].values())
        / report["counts"]["agent_cases"]
    )
    report["gates"] = release_gates(report["metrics"], "stub", [])
    report["passed"] = False
    report["failure_count"] = 1
    destination = tmp_path / "stub-on/report.json"
    destination.parent.mkdir()
    destination.write_text(json.dumps(report))
    published = json.loads(evidence_snapshot(tmp_path))["runs"][0]["report"]
    assert not published["passed"]
    assert not published["gates"]["false_allocation_rate"]
    assert published["failure_count"] == 1
