"""Layer 4 — Churn early-warning system.

Builds a customer feature table (RFM + behavioral + cohort) and trains
a logistic + gradient-boosted classifier to predict churn, defined as
>= `inactivity_days` since last order at the snapshot date.

The model outputs per-customer risk scores, a segment-level summary,
and calibration / ROC metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from pulsecommerce.config import CHURN
from pulsecommerce.logging_utils import get_logger
from pulsecommerce.warehouse import Warehouse

logger = get_logger(__name__)


NUMERIC_COLS = [
    "age",
    "tenure_days",
    "recency_days",
    "frequency",
    "monetary",
    "avg_order_value",
    "distinct_categories",
    "cancel_rate",
    "days_between_orders",
]
CAT_COLS = ["country", "traffic_source"]


@dataclass
class ChurnReport:
    snapshot_date: date
    metrics: dict[str, float]
    scores: pd.DataFrame  # user_id, churn_risk, decile
    cohort_retention: pd.DataFrame
    feature_importance: pd.DataFrame


class ChurnModel:
    def __init__(self, warehouse: Warehouse, cfg=CHURN):
        self.wh = warehouse
        self.cfg = cfg

    # --------------------------------------------------------------------- #
    # Data preparation
    # --------------------------------------------------------------------- #
    def _snapshot_date(self) -> date:
        df = self.wh.query("SELECT MAX(order_date) AS d FROM fct_orders")
        return pd.to_datetime(df.loc[0, "d"]).date()

    def build_features(self, snapshot: date | None = None) -> pd.DataFrame:
        """Point-in-time feature build with correct label/feature separation.

        Features are computed from orders on/before `feature_cutoff = snapshot - inactivity_days`.
        The label is whether the user purchased AGAIN between feature_cutoff and snapshot.
        This prevents the trivial leakage of using recency as both feature and label.
        """
        snapshot = snapshot or self._snapshot_date()
        feature_cutoff = snapshot - timedelta(days=self.cfg.inactivity_days)

        df = self.wh.query(
            """
            WITH feat_orders AS (
                SELECT o.*
                FROM fct_orders o
                WHERE o.status NOT IN ('Cancelled','Returned')
                  AND o.order_date <= ?
            ),
            future_orders AS (
                SELECT DISTINCT user_id
                FROM fct_orders
                WHERE status NOT IN ('Cancelled','Returned')
                  AND order_date > ?
                  AND order_date <= ?
            ),
            user_items AS (
                SELECT user_id, COUNT(DISTINCT category) AS distinct_categories
                FROM stg_order_items
                WHERE status NOT IN ('Cancelled','Returned')
                  AND item_date <= ?
                GROUP BY user_id
            ),
            user_cancels AS (
                SELECT user_id, AVG(is_lost) AS cancel_rate
                FROM fct_orders
                WHERE order_date <= ?
                GROUP BY user_id
            ),
            agg AS (
                SELECT
                    u.user_id,
                    u.age,
                    u.country,
                    u.traffic_source,
                    DATE_DIFF('day', u.signed_up_at, ?) AS tenure_days,
                    MAX(fo.order_date)                    AS last_order_date,
                    COUNT(fo.order_id)                    AS frequency,
                    SUM(fo.order_revenue)                 AS monetary,
                    AVG(fo.order_revenue)                 AS avg_order_value,
                    CASE WHEN COUNT(fo.order_id) > 1
                         THEN DATE_DIFF('day', MIN(fo.order_date), MAX(fo.order_date))
                              * 1.0 / GREATEST(COUNT(fo.order_id) - 1, 1)
                         ELSE NULL END AS days_between_orders
                FROM dim_customers u
                LEFT JOIN feat_orders fo ON u.user_id = fo.user_id
                GROUP BY u.user_id, u.age, u.country, u.traffic_source, u.signed_up_at
            )
            SELECT
                a.*,
                COALESCE(ui.distinct_categories, 0) AS distinct_categories,
                COALESCE(uc.cancel_rate, 0)         AS cancel_rate,
                DATE_DIFF('day', a.last_order_date, ?) AS recency_days,
                CASE WHEN fu.user_id IS NOT NULL THEN 0 ELSE 1 END AS churned
            FROM agg a
            LEFT JOIN user_items ui  ON a.user_id = ui.user_id
            LEFT JOIN user_cancels uc ON a.user_id = uc.user_id
            LEFT JOIN future_orders fu ON a.user_id = fu.user_id
            WHERE a.frequency > 0
            """,
            [
                feature_cutoff,
                feature_cutoff,
                snapshot,
                feature_cutoff,
                feature_cutoff,
                feature_cutoff,
                feature_cutoff,
            ],
        )

        if df.empty:
            return df

        df["avg_order_value"] = df["avg_order_value"].fillna(
            df["monetary"] / df["frequency"].clip(lower=1)
        )
        df["days_between_orders"] = df["days_between_orders"].fillna(df["tenure_days"])
        df["recency_days"] = df["recency_days"].fillna(df["tenure_days"])
        return df

    # --------------------------------------------------------------------- #
    # Training
    # --------------------------------------------------------------------- #
    def _build_pipeline(self) -> Pipeline:
        pre = ColumnTransformer(
            transformers=[
                ("num", StandardScaler(), NUMERIC_COLS),
                ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), CAT_COLS),
            ]
        )
        model = XGBClassifier(
            n_estimators=400,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=self.cfg.random_state,
            verbosity=0,
            tree_method="hist",
        )
        return Pipeline([("pre", pre), ("model", model)])

    def fit_and_score(self, snapshot: date | None = None) -> ChurnReport:
        snapshot = snapshot or self._snapshot_date()
        df = self.build_features(snapshot=snapshot)
        if df.empty or df["churned"].nunique() < 2:
            raise ValueError("Not enough signal to train a churn model.")

        y = df["churned"].to_numpy()
        X = df[NUMERIC_COLS + CAT_COLS].copy()

        # stratify only when every class has at least 2 samples
        class_counts = pd.Series(y).value_counts()
        stratify = y if class_counts.min() >= 2 else None
        if stratify is None:
            logger.warning(
                "class imbalance prevents stratified split (counts=%s); falling back to random split",
                class_counts.to_dict(),
            )
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.cfg.test_size,
            random_state=self.cfg.random_state,
            stratify=stratify,
        )
        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            raise ValueError(
                f"train/test split produced a single-class set "
                f"(train={sorted(set(y_train))}, test={sorted(set(y_test))}); "
                f"need more data or a longer churn window"
            )
        pipe = self._build_pipeline()
        pipe.fit(X_train, y_train)

        proba_test = pipe.predict_proba(X_test)[:, 1]
        auc = float(roc_auc_score(y_test, proba_test))
        ap = float(average_precision_score(y_test, proba_test))

        # baseline logistic for interpretability
        lr_pipe = Pipeline(
            [
                (
                    "pre",
                    ColumnTransformer(
                        transformers=[
                            ("num", StandardScaler(), NUMERIC_COLS),
                            (
                                "cat",
                                OneHotEncoder(handle_unknown="ignore", min_frequency=50),
                                CAT_COLS,
                            ),
                        ]
                    ),
                ),
                ("model", LogisticRegression(max_iter=1000, random_state=self.cfg.random_state)),
            ]
        )
        lr_pipe.fit(X_train, y_train)
        lr_auc = float(roc_auc_score(y_test, lr_pipe.predict_proba(X_test)[:, 1]))

        proba_all = pipe.predict_proba(X)[:, 1]
        scores = pd.DataFrame(
            {
                "user_id": df["user_id"].to_numpy(),
                "churn_risk": proba_all,
                "actual_churn": y,
                "recency_days": df["recency_days"].to_numpy(),
                "frequency": df["frequency"].to_numpy(),
                "monetary": df["monetary"].to_numpy(),
                "country": df["country"].to_numpy(),
            }
        )
        scores["risk_decile"] = (
            pd.qcut(
                scores["churn_risk"].rank(method="first"), q=10, labels=False, duplicates="drop"
            )
            + 1
        )

        # feature importance (from xgb inside pipeline)
        model = pipe.named_steps["model"]
        pre_fitted = pipe.named_steps["pre"]
        try:
            feature_names = pre_fitted.get_feature_names_out()
        except Exception:
            feature_names = np.array(NUMERIC_COLS + CAT_COLS)
        importances = getattr(model, "feature_importances_", np.zeros(len(feature_names)))
        importance_df = (
            pd.DataFrame({"feature": feature_names, "importance": importances})
            .sort_values("importance", ascending=False)
            .head(20)
            .reset_index(drop=True)
        )

        cohort_retention = self._cohort_retention(snapshot)

        metrics = {
            "roc_auc_xgb": auc,
            "average_precision_xgb": ap,
            "roc_auc_logreg": lr_auc,
            "train_rows": int(len(y_train)),
            "test_rows": int(len(y_test)),
            "churn_rate": float(y.mean()),
            "snapshot": snapshot.isoformat(),
        }
        logger.info(
            "churn model trained — AUC=%.3f (xgb) / %.3f (logreg), AP=%.3f",
            auc,
            lr_auc,
            ap,
        )
        return ChurnReport(
            snapshot_date=snapshot,
            metrics=metrics,
            scores=scores,
            cohort_retention=cohort_retention,
            feature_importance=importance_df,
        )

    # --------------------------------------------------------------------- #
    # Cohort retention
    # --------------------------------------------------------------------- #
    def _cohort_retention(self, snapshot: date) -> pd.DataFrame:
        df = self.wh.query(
            """
            WITH first_order AS (
                SELECT user_id, MIN(order_date) AS cohort_start
                FROM fct_orders
                WHERE status NOT IN ('Cancelled','Returned')
                GROUP BY user_id
            )
            SELECT
                DATE_TRUNC('month', f.cohort_start) AS cohort_month,
                DATE_DIFF('month', f.cohort_start, o.order_date) AS month_number,
                COUNT(DISTINCT o.user_id) AS active_users
            FROM fct_orders o
            JOIN first_order f ON o.user_id = f.user_id
            WHERE o.status NOT IN ('Cancelled','Returned')
              AND o.order_date <= ?
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            [snapshot],
        )
        if df.empty:
            return df
        cohort_sizes = df[df["month_number"] == 0][["cohort_month", "active_users"]].rename(
            columns={"active_users": "cohort_size"}
        )
        df = df.merge(cohort_sizes, on="cohort_month", how="left")
        df["retention_rate"] = df["active_users"] / df["cohort_size"]
        return df
