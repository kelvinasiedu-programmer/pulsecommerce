from pulsecommerce.analytics.funnel import FUNNEL_STAGES, FunnelAnalyst


def test_funnel_overall_monotone(warehouse):
    df = FunnelAnalyst(warehouse).overall()
    assert list(df["stage"]) == list(FUNNEL_STAGES)
    counts = df["count"].tolist()
    assert all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1))


def test_funnel_insights_structure(warehouse):
    ins = FunnelAnalyst(warehouse).insights()
    assert ins.biggest_drop_stage in FUNNEL_STAGES
    assert 0.0 <= ins.biggest_drop_rate <= 1.0
    assert ins.estimated_lost_revenue >= 0.0
