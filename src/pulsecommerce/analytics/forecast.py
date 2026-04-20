"""Layer 3 — Demand forecasting with seasonal + ML models.

Three forecasters compete on the same weekly category-level data:
  * Seasonal naive  (baseline — last-year-same-week)
  * Holt-Winters exponential smoothing (statsmodels)
  * Gradient boosted trees on lag + calendar features (XGBoost)

The winner per category is selected via walk-forward MAPE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from xgboost import XGBRegressor

from pulsecommerce.config import FORECAST
from pulsecommerce.logging_utils import get_logger
from pulsecommerce.warehouse import Warehouse

logger = get_logger(__name__)


@dataclass
class ForecastResult:
    category: str
    history: pd.DataFrame  # week_start, revenue, units_sold
    forecast: pd.DataFrame  # week_start, yhat, yhat_lower, yhat_upper, model
    backtest_mape: dict[str, float]
    chosen_model: str


def _make_features(series: pd.Series) -> pd.DataFrame:
    df = series.to_frame("y").copy()
    df["week_of_year"] = df.index.isocalendar().week.astype(int)
    df["month"] = df.index.month
    df["quarter"] = df.index.quarter
    df["t"] = np.arange(len(df))
    for lag in (1, 2, 4, 8, 13, 26, 52):
        df[f"lag_{lag}"] = df["y"].shift(lag)
    df["roll4_mean"] = df["y"].shift(1).rolling(4).mean()
    df["roll8_mean"] = df["y"].shift(1).rolling(8).mean()
    df["roll4_std"] = df["y"].shift(1).rolling(4).std()
    return df


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def _fit_seasonal_naive(series: pd.Series, horizon: int) -> np.ndarray:
    if len(series) < 52:
        tail = series.tail(horizon).to_numpy()
        if len(tail) < horizon:
            tail = np.concatenate([tail, np.repeat(series.iloc[-1], horizon - len(tail))])
        return tail
    return series.shift(52).tail(horizon).to_numpy()


def _fit_holt_winters(series: pd.Series, horizon: int) -> np.ndarray:
    try:
        s = series.astype(float)
        if isinstance(s.index, pd.DatetimeIndex) and s.index.freq is None:
            s = s.asfreq("W-MON")
            s = s.ffill()
        model = ExponentialSmoothing(
            s,
            trend="add",
            seasonal="add" if len(series) >= 104 else None,
            seasonal_periods=52 if len(series) >= 104 else None,
            initialization_method="estimated",
        ).fit(optimized=True, use_brute=True)
        return np.asarray(model.forecast(horizon))
    except Exception as exc:  # pragma: no cover
        logger.warning("holt-winters failed: %s", exc)
        return np.repeat(series.iloc[-1], horizon)


def _fit_xgb(series: pd.Series, horizon: int) -> np.ndarray:
    feats = _make_features(series).dropna()
    if feats.empty:
        return np.repeat(series.iloc[-1], horizon)
    X, y = feats.drop(columns="y"), feats["y"]
    model = XGBRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        verbosity=0,
    )
    model.fit(X, y)

    history = series.copy()
    preds = []
    for _ in range(horizon):
        feats_all = _make_features(history)
        x_next = feats_all.drop(columns="y").iloc[[-1]]
        if x_next.isna().any(axis=None):
            yhat = history.iloc[-1]
        else:
            yhat = float(model.predict(x_next)[0])
        preds.append(yhat)
        next_index = history.index[-1] + pd.Timedelta(weeks=1)
        history = pd.concat([history, pd.Series([yhat], index=[next_index])])
    return np.array(preds)


class DemandForecaster:
    def __init__(self, warehouse: Warehouse, horizon_weeks: int = FORECAST.horizon_weeks):
        self.wh = warehouse
        self.horizon = horizon_weeks

    def load_history(self) -> pd.DataFrame:
        df = self.wh.query(
            "SELECT week_start, category, revenue, units_sold FROM weekly_category ORDER BY week_start"
        )
        df["week_start"] = pd.to_datetime(df["week_start"])
        return df

    def forecast_category(
        self, category: str, history: pd.DataFrame | None = None
    ) -> ForecastResult:
        if history is None:
            history = self.load_history()
        hist = history[history["category"] == category].set_index("week_start").sort_index()
        series = hist["revenue"].astype(float)
        if len(series) < FORECAST.min_history_weeks:
            raise ValueError(
                f"Not enough history for {category}: {len(series)} weeks "
                f"(need {FORECAST.min_history_weeks})"
            )

        # walk-forward backtest
        folds = FORECAST.backtest_folds
        fold_size = max(4, self.horizon)
        scores: dict[str, list[float]] = {"seasonal_naive": [], "holt_winters": [], "xgboost": []}
        for i in range(folds, 0, -1):
            split = len(series) - i * fold_size
            if split <= FORECAST.min_history_weeks:
                continue
            train, test = series.iloc[:split], series.iloc[split : split + fold_size]
            scores["seasonal_naive"].append(
                _mape(test.to_numpy(), _fit_seasonal_naive(train, len(test)))
            )
            scores["holt_winters"].append(
                _mape(test.to_numpy(), _fit_holt_winters(train, len(test)))
            )
            scores["xgboost"].append(_mape(test.to_numpy(), _fit_xgb(train, len(test))))

        mape = {
            name: float(np.nanmean(vals)) if vals else float("nan") for name, vals in scores.items()
        }
        chosen = min(
            (k for k, v in mape.items() if not np.isnan(v)),
            key=lambda k: mape[k],
            default="seasonal_naive",
        )

        model_fn = {
            "seasonal_naive": _fit_seasonal_naive,
            "holt_winters": _fit_holt_winters,
            "xgboost": _fit_xgb,
        }[chosen]
        yhat = model_fn(series, self.horizon)

        last_ts = series.index[-1]
        future_index = [last_ts + timedelta(weeks=i + 1) for i in range(self.horizon)]
        residual_std = series.diff().std() or float(series.std() or 1.0)
        z = 1.96
        forecast_df = pd.DataFrame(
            {
                "week_start": future_index,
                "yhat": yhat,
                "yhat_lower": yhat - z * residual_std,
                "yhat_upper": yhat + z * residual_std,
                "model": chosen,
            }
        )

        return ForecastResult(
            category=category,
            history=hist.reset_index()[["week_start", "revenue", "units_sold"]],
            forecast=forecast_df,
            backtest_mape=mape,
            chosen_model=chosen,
        )

    def forecast_all(self) -> list[ForecastResult]:
        history = self.load_history()
        results = []
        for cat in sorted(history["category"].unique()):
            try:
                results.append(self.forecast_category(cat, history=history))
            except ValueError as exc:
                logger.warning("skipping %s: %s", cat, exc)
        return results
