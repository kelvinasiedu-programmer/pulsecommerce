import numpy as np
import pytest

from pulsecommerce.analytics.experiment import (
    MetricResult,
    PromotionExperiment,
    _apply_relative_lift,
    _assign_arms_balanced,
    _decide,
)


def test_balanced_assignment_levels_the_pre_treatment_rate():
    rng = np.random.default_rng(3)
    converted = np.array([1] * 121 + [0] * 4001)
    arms = _assign_arms_balanced(converted, rng)
    for value in (0, 1):
        in_stratum = arms[converted == value]
        n_ctrl = int((in_stratum == "control").sum())
        n_trt = int((in_stratum == "treatment").sum())
        assert abs(n_ctrl - n_trt) <= 1, f"stratum {value} split {n_ctrl}/{n_trt}"
    assert converted[arms == "control"].mean() == pytest.approx(
        converted[arms == "treatment"].mean(), abs=0.002
    )


def test_relative_lift_never_unconverts_an_existing_converter():
    base = np.array([1.0] * 50 + [0.0] * 50)
    out = _apply_relative_lift(base, lift=0.08, rng=np.random.default_rng(0))
    assert out[base == 1].all(), "a converted user must stay converted"


def test_relative_lift_moves_rate_by_the_requested_proportion():
    rng = np.random.default_rng(7)
    base = (rng.random(200_000) < 0.03).astype(float)
    out = _apply_relative_lift(base, lift=0.08, rng=rng)
    expected = base.mean() * 1.08
    assert out.mean() == pytest.approx(expected, rel=0.05)


def test_relative_lift_is_a_noop_on_degenerate_rates():
    rng = np.random.default_rng(1)
    all_zero = np.zeros(100)
    all_one = np.ones(100)
    assert _apply_relative_lift(all_zero, 0.08, rng).sum() == 0
    assert _apply_relative_lift(all_one, 0.08, rng).sum() == 100


def test_experiment_produces_recommendation(warehouse):
    exp = PromotionExperiment(warehouse, treatment_effect=0.15).run(window_days=90)
    assert exp.recommendation in {"ship", "iterate", "reject"}
    assert exp.primary.name == "conversion_rate"
    names = {g.name for g in exp.guardrails}
    assert {"average_order_value", "items_per_order", "refund_rate_proxy"} == names


def _metric(name, mean_ctrl, mean_trt, p, guardrail, lower_is_better):
    abs_lift = mean_trt - mean_ctrl
    rel_lift = abs_lift / mean_ctrl if mean_ctrl else 0.0
    direction_ok = (abs_lift <= 0) if lower_is_better else (abs_lift >= 0)
    return MetricResult(
        name=name,
        control_mean=mean_ctrl,
        treatment_mean=mean_trt,
        abs_lift=abs_lift,
        rel_lift=rel_lift,
        p_value=p,
        is_significant=p < 0.05,
        is_guardrail=guardrail,
        direction_ok=direction_ok,
    )


def test_decide_rejects_when_guardrail_breaches():
    primary = _metric("conv", 0.10, 0.12, p=0.01, guardrail=False, lower_is_better=False)
    guardrails = [
        _metric("aov", 50.0, 40.0, p=0.001, guardrail=True, lower_is_better=False),
        _metric("refund", 0.05, 0.05, p=0.9, guardrail=True, lower_is_better=True),
    ]
    rec, _ = _decide(primary, guardrails)
    assert rec == "reject"


def test_decide_ships_on_clean_primary_win():
    primary = _metric("conv", 0.10, 0.12, p=0.01, guardrail=False, lower_is_better=False)
    guardrails = [
        _metric("aov", 50.0, 51.0, p=0.3, guardrail=True, lower_is_better=False),
        _metric("refund", 0.05, 0.05, p=0.9, guardrail=True, lower_is_better=True),
    ]
    rec, _ = _decide(primary, guardrails)
    assert rec == "ship"


def test_decide_iterates_on_directional_but_insignificant_primary():
    primary = _metric("conv", 0.10, 0.105, p=0.3, guardrail=False, lower_is_better=False)
    rec, _ = _decide(primary, guardrails=[])
    assert rec == "iterate"
