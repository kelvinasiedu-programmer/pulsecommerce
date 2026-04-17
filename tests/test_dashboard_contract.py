from pathlib import Path

from pulsecommerce.analytics.health import HealthAnalyst


def test_health_cards_expose_stable_metric_ids(warehouse):
    report = HealthAnalyst(warehouse).report(window_days=28)
    metric_ids = {card.metric_id for card in report.cards}
    assert {"revenue", "orders", "sessions", "aov", "conversion_rate"} <= metric_ids


def test_home_page_links_do_not_use_plain_arrow_icons():
    home_py = Path(__file__).resolve().parents[1] / "dashboard" / "Home.py"
    source = home_py.read_text(encoding="utf-8")
    assert 'icon="→"' not in source
