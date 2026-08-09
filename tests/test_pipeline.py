import pandas as pd

from pulsecommerce.config import EXPERIMENT
from pulsecommerce.pipeline import _promo_audience


def _scores(risks: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"user_id": range(1, len(risks) + 1), "churn_risk": risks},
    )


def test_promo_audience_keeps_only_the_at_risk_but_active_band():
    """The top decile has already left and is useless to test on.

    Targeting `nlargest(30%)` sounded right and produced an audience converting
    at 0.32% - 7 purchases across both arms, where one customer flipped the
    verdict between iterate and reject. The band excludes both the safe
    customers and the ones already gone.
    """
    floor, ceiling = EXPERIMENT.audience_risk_floor, EXPERIMENT.audience_risk_ceiling
    below = [floor - 0.1] * 200
    inside = [floor + 0.05] * EXPERIMENT.min_sample_size
    above = [ceiling + 0.1] * 3_000

    audience = _promo_audience(_scores(below + inside + above))

    assert audience is not None
    assert len(audience) == EXPERIMENT.min_sample_size
    assert list(audience.columns) == ["user_id"]


def test_promo_audience_declines_to_target_when_the_band_is_too_thin():
    """Better untargeted than a verdict drawn from a handful of purchases."""
    floor = EXPERIMENT.audience_risk_floor
    thin = [floor + 0.05] * (EXPERIMENT.min_sample_size - 1)

    assert _promo_audience(_scores(thin + [0.99] * 5_000)) is None


def test_promo_audience_band_is_bounded_and_ordered():
    assert 0.0 < EXPERIMENT.audience_risk_floor < EXPERIMENT.audience_risk_ceiling < 1.0
