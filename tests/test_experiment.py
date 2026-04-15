from pulsecommerce.analytics.experiment import PromotionExperiment


def test_experiment_produces_recommendation(warehouse):
    exp = PromotionExperiment(warehouse, treatment_effect=0.15).run(window_days=90)
    assert exp.recommendation in {"ship", "iterate", "reject"}
    assert exp.primary.name == "conversion_rate"
    names = {g.name for g in exp.guardrails}
    assert {"average_order_value", "items_per_order", "refund_rate_proxy"} == names


def test_experiment_respects_guardrails(warehouse):
    """A huge negative drift on guardrails should never recommend ship."""
    exp = PromotionExperiment(warehouse, treatment_effect=0.10, guardrail_drift=-0.25).run(
        window_days=90
    )
    if exp.primary.is_significant and exp.primary.rel_lift > 0:
        assert exp.recommendation in {"reject", "iterate"}
