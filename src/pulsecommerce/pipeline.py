"""Top-level pipeline that runs all 5 analytical layers and persists results.

Outputs:
  data/processed/kpi_cards.parquet
  data/processed/kpi_daily.parquet
  data/processed/funnel_overall.parquet
  data/processed/funnel_segmented.parquet
  data/processed/forecast.parquet
  data/processed/churn_scores.parquet
  data/processed/churn_metrics.json
  data/processed/cohort_retention.parquet
  data/processed/experiment.json
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from pulsecommerce.analytics.churn import ChurnModel
from pulsecommerce.analytics.experiment import PromotionExperiment
from pulsecommerce.analytics.forecast import DemandForecaster
from pulsecommerce.analytics.funnel import FunnelAnalyst
from pulsecommerce.analytics.health import HealthAnalyst
from pulsecommerce.config import PROCESSED_DIR, ensure_dirs
from pulsecommerce.logging_utils import get_logger
from pulsecommerce.warehouse import Warehouse

logger = get_logger(__name__)


def run_pipeline(out_dir: Path = PROCESSED_DIR) -> dict[str, Path]:
    ensure_dirs()
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    with Warehouse() as wh:
        # 1. Health
        logger.info("layer 1 — computing health KPIs")
        report = HealthAnalyst(wh).report(window_days=28)
        cards_df = pd.DataFrame([c.to_dict() for c in report.cards])
        paths["kpi_cards"] = _write(cards_df, out_dir / "kpi_cards.parquet")
        paths["kpi_daily"] = _write(report.daily, out_dir / "kpi_daily.parquet")
        paths["kpi_channel"] = _write(report.by_channel, out_dir / "kpi_channel.parquet")
        paths["kpi_category"] = _write(report.by_category, out_dir / "kpi_category.parquet")

        # 2. Funnel
        logger.info("layer 2 — computing funnel")
        funnel = FunnelAnalyst(wh)
        paths["funnel_overall"] = _write(funnel.overall(), out_dir / "funnel_overall.parquet")
        paths["funnel_segmented"] = _write(
            funnel.by_segment(), out_dir / "funnel_segmented.parquet"
        )
        insight = funnel.insights()
        _write_json(asdict(insight), out_dir / "funnel_insights.json")
        paths["funnel_insights"] = out_dir / "funnel_insights.json"

        # 3. Forecast
        logger.info("layer 3 — running forecasts")
        forecaster = DemandForecaster(wh)
        forecast_rows = []
        mape_rows = []
        for res in forecaster.forecast_all():
            hist = res.history.assign(category=res.category, kind="history")
            fc = res.forecast.assign(category=res.category, kind="forecast")
            forecast_rows.append(
                hist.rename(columns={"revenue": "yhat"}).assign(
                    yhat_lower=None, yhat_upper=None, model=None
                )
            )
            forecast_rows.append(fc)
            mape_rows.append(
                {"category": res.category, "chosen_model": res.chosen_model, **res.backtest_mape}
            )
        forecast_df = (
            pd.concat(forecast_rows, ignore_index=True) if forecast_rows else pd.DataFrame()
        )
        paths["forecast"] = _write(forecast_df, out_dir / "forecast.parquet")
        paths["forecast_mape"] = _write(pd.DataFrame(mape_rows), out_dir / "forecast_mape.parquet")

        # 4. Churn
        logger.info("layer 4 — training churn model")
        churn = None
        try:
            churn = ChurnModel(wh).fit_and_score()
            paths["churn_scores"] = _write(churn.scores, out_dir / "churn_scores.parquet")
            paths["cohort_retention"] = _write(
                churn.cohort_retention, out_dir / "cohort_retention.parquet"
            )
            paths["churn_importance"] = _write(
                churn.feature_importance, out_dir / "churn_importance.parquet"
            )
            _write_json(churn.metrics, out_dir / "churn_metrics.json")
            paths["churn_metrics"] = out_dir / "churn_metrics.json"
        except (ValueError, RuntimeError) as exc:
            logger.warning("skipping churn layer — insufficient signal: %s", exc)
            _write_json({"skipped": True, "reason": str(exc)}, out_dir / "churn_metrics.json")
            paths["churn_metrics"] = out_dir / "churn_metrics.json"

        # 5. Experiment on top-risk customers (or untargeted if churn skipped)
        logger.info("layer 5 — running simulated experiment readout")
        if churn is not None:
            audience = churn.scores.nlargest(max(int(len(churn.scores) * 0.3), 500), "churn_risk")[
                ["user_id"]
            ]
        else:
            audience = None
        exp = PromotionExperiment(wh).run(audience=audience)
        _write_json(
            {
                "hypothesis": exp.hypothesis,
                "start": exp.start.isoformat(),
                "end": exp.end.isoformat(),
                "n_control": exp.n_control,
                "n_treatment": exp.n_treatment,
                "primary": asdict(exp.primary),
                "guardrails": [asdict(g) for g in exp.guardrails],
                "recommendation": exp.recommendation,
                "rationale": exp.rationale,
            },
            out_dir / "experiment.json",
        )
        paths["experiment"] = out_dir / "experiment.json"

    logger.info("pipeline complete — %d artifacts written", len(paths))
    return paths


def _write(df: pd.DataFrame, path: Path) -> Path:
    df.to_parquet(path, index=False)
    return path


def _write_json(payload: dict, path: Path) -> Path:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
