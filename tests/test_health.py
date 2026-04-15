from pulsecommerce.analytics.health import HealthAnalyst


def test_health_report(warehouse):
    report = HealthAnalyst(warehouse).report(window_days=14)
    assert report.window_days == 14
    labels = {c.label for c in report.cards}
    assert {"Revenue", "Orders", "AOV", "Conversion Rate"} <= labels
    assert not report.daily.empty
