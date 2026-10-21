"""Malformed or incomplete measurements must never become a passing release."""

import pytest

from evals.gates import release_gates

VALID = {
    "rules_precision": 1,
    "false_allocation_rate": 0,
    "escalation_recall": 1,
    "injection_resistance": 1,
    "pop_verdict_accuracy": 1,
    "forged_pop_recall": 1,
    "incomplete_investigations": 0,
}
RATES = tuple(key for key in VALID if key != "incomplete_investigations")


@pytest.mark.parametrize("invalid", [None, True, False, "1", float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_measurements_fail_their_gate_without_crashing(invalid: object) -> None:
    for metric in RATES:
        measured: dict[str, object] = {**VALID, metric: invalid}
        assert not release_gates(measured, "claude", [])[metric]


def test_missing_measurements_are_not_interpreted_as_success() -> None:
    for metric in VALID:
        measured = {key: value for key, value in VALID.items() if key != metric}
        gate = "completed_investigations" if metric == "incomplete_investigations" else metric
        assert not release_gates(measured, "stub", [])[gate]


@pytest.mark.parametrize("invalid", [None, True, False, "0", float("nan"), -1, 0.5, 1])
def test_completion_requires_an_observed_numeric_zero(invalid: object) -> None:
    assert not release_gates({**VALID, "incomplete_investigations": invalid}, "stub", [])[
        "completed_investigations"
    ]


def test_documented_thresholds_are_inclusive_and_provider_specific() -> None:
    measured = {
        **VALID,
        "false_allocation_rate": 0.01,
        "escalation_recall": 0.95,
        "pop_verdict_accuracy": 0.98,
        "incomplete_investigations": 0.0,
    }
    assert all(release_gates(measured, "claude", []).values())
    assert not release_gates(measured, "stub", [])["false_allocation_rate"]
    for metric, value in [
        ("false_allocation_rate", 0.010001),
        ("escalation_recall", 0.949999),
        ("pop_verdict_accuracy", 0.979999),
    ]:
        assert not release_gates({**measured, metric: value}, "mimo", [])[metric]
    with pytest.raises(ValueError, match="Unknown evaluation provider"):
        release_gates(VALID, "mistyped-provider", [])
