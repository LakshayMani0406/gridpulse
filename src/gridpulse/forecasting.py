"""Weather-aware demand forecasting comparison.

Runs the rolling-origin backtest for one BA twice -- calendar+lag features only,
then with Open-Meteo degree-hour features added -- and reports the forecast-skill
improvement. Leakage guards (causal features, expanding-window folds) are intact
in both runs.
"""
from __future__ import annotations

import json
import logging


from .config import Config, load_config
from .docs_util import upsert_section
from .model import rolling_origin_backtest
from .storage import Warehouse
from .weather import WEATHER_FEATURES, attach_weather

log = logging.getLogger("gridpulse.forecasting")


def run_forecast_comparison(cfg: Config | None = None, ba: str = "ERCO",
                            n_folds: int = 12, horizon: int = 168) -> dict:
    cfg = cfg or load_config()
    wh = Warehouse(cfg)
    dem = wh.read("demand")
    if dem.empty:
        raise RuntimeError("no demand in warehouse; run backfill first")
    s = dem[dem["ba"] == ba][["period", "mwh"]].rename(columns={"mwh": "demand_mwh"})
    s = s.sort_values("period").reset_index(drop=True)
    if len(s) < 24 * 45:
        raise RuntimeError(f"insufficient demand history for {ba} ({len(s)} h)")

    base = rolling_origin_backtest(s, n_folds=n_folds, horizon=horizon)
    sw = attach_weather(cfg, s, ba)
    wx = rolling_origin_backtest(sw, n_folds=n_folds, horizon=horizon,
                                 extra_features=WEATHER_FEATURES)

    improvement = (
        1 - wx["model_mae"] / base["model_mae"] if base.get("model_mae") else float("nan")
    )
    result = {
        "ba": ba,
        "n_folds": base["n_folds"],
        "naive_mae": base["naive_mae"],
        "model_mae_no_weather": base["model_mae"],
        "model_mae_weather": wx["model_mae"],
        "weather_mae_improvement_pct": 100 * improvement,
        "skill_vs_naive_no_weather": base["skill_vs_naive"],
        "skill_vs_naive_weather": wx["skill_vs_naive"],
        "coverage80_weather": wx["model_coverage_80"],
    }
    _write_evidence(cfg, result)
    log.info("forecast %s: MAE %.0f -> %.0f with weather (%.1f%% better)",
             ba, base["model_mae"], wx["model_mae"], 100 * improvement)
    return result


def _write_evidence(cfg: Config, r: dict) -> None:
    title = f"Phase B: weather-aware forecasting ({r['ba']})"
    section = [
        f"## {title}",
        "",
        f"Rolling-origin backtest ({r['n_folds']} folds, weekly horizon), "
        "HistGB quantile model. Weather = Open-Meteo degree-hours (cooling/heating) "
        "at the BA load center. Leakage guards (causal features, expanding folds) intact.",
        "",
        f"- Seasonal-naive MAE: **{r['naive_mae']:.0f} MWh**",
        f"- Model MAE (calendar+lag): **{r['model_mae_no_weather']:.0f} MWh** "
        f"(skill vs naive {r['skill_vs_naive_no_weather']*100:.0f}%)",
        f"- Model MAE (+ weather): **{r['model_mae_weather']:.0f} MWh** "
        f"(skill vs naive {r['skill_vs_naive_weather']*100:.0f}%)",
        f"- **Weather feature gain: {r['weather_mae_improvement_pct']:.1f}% lower MAE**",
        f"- 80% conformal-band coverage (weather model): {r['coverage80_weather']*100:.0f}%",
        "",
    ]
    upsert_section(cfg.repo_root / "EVIDENCE.md", title, "\n".join(section),
                   doc_header="# gridpulse EVIDENCE")
    (cfg.figs_dir.parent / "forecast_weather.json").write_text(json.dumps(r, indent=2))
