from pulsecommerce.analytics.health import HealthAnalyst


def test_health_cards_expose_stable_metric_ids(warehouse):
    report = HealthAnalyst(warehouse).report(window_days=28)
    metric_ids = {card.metric_id for card in report.cards}
    assert {"revenue", "orders", "sessions", "aov", "conversion_rate"} <= metric_ids
