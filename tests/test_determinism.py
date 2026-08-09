"""Guards against unordered SQL feeding position-dependent code.

DuckDB parallelises joins and aggregations, so a query without ORDER BY returns
rows in whatever order the threads finish. Two consumers here split by position
rather than by key - `train_test_split` in the churn model and the arm shuffle in
the experiment - so a reshuffle silently retrains on a different split or puts
different customers in different arms.

That is not theoretical. Two consecutive runs on identical data produced
different churn scores, which moved customers in and out of the experiment's
risk band, and a commit touching only documentation flipped the published
verdict from iterate to reject.
"""

from __future__ import annotations

import pandas as pd

from pulsecommerce.analytics.churn import ChurnModel
from pulsecommerce.analytics.experiment import PromotionExperiment


def test_churn_features_come_back_in_a_stable_order(warehouse):
    features = ChurnModel(warehouse).build_features()

    assert features["user_id"].is_monotonic_increasing, (
        "churn feature query lost its ORDER BY; train_test_split partitions by "
        "position, so the model would retrain on a different split each run"
    )


def test_experiment_panel_comes_back_in_a_stable_order(warehouse):
    panel = PromotionExperiment(warehouse)._bootstrap_user_panel()

    assert panel["user_id"].is_monotonic_increasing, (
        "experiment panel query lost its ORDER BY; arm assignment shuffles by "
        "position, so customers would land in different arms each run"
    )


def test_churn_scores_are_reproducible_across_runs(warehouse):
    """The end-to-end check. Same warehouse in, byte-identical scores out."""
    first = ChurnModel(warehouse).fit_and_score().scores
    second = ChurnModel(warehouse).fit_and_score().scores

    pd.testing.assert_frame_equal(first, second)
