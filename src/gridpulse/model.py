"""Demand forecasting: leakage-safe features, quantile model, backtest, conformal.

- Features are strictly causal: calendar terms plus lags/rolling stats that only
  look backward, so a rolling-origin backtest cannot leak the future.
- The point/quantile model is a gradient-boosted quantile regressor (sklearn)
  with a seasonal-naive baseline for reference.
- Uncertainty is calibrated with Conformalized Quantile Regression (CQR,
  Romano et al. 2019) to get finite-sample coverage guarantees.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import HAS_SKLEARN

log = logging.getLogger("gridpulse.model")

SEASONAL_LAG = 168  # one week of hours


# --------------------------------------------------------------- features
def make_features(series: pd.DataFrame, target: str = "demand_mwh") -> pd.DataFrame:
    """Build leakage-safe features from a single-BA hourly demand series.

    ``series`` needs ``period`` (parseable) and ``target``. All engineered
    features use only information available strictly before each timestamp.
    """
    s = series.copy()
    s["period"] = pd.to_datetime(s["period"])
    s = s.sort_values("period").reset_index(drop=True)
    t = s["period"].dt

    s["hour"] = t.hour
    s["dow"] = t.dayofweek
    s["month"] = t.month
    s["is_weekend"] = (t.dayofweek >= 5).astype(int)
    # Cyclical encodings.
    s["hour_sin"] = np.sin(2 * np.pi * s["hour"] / 24)
    s["hour_cos"] = np.cos(2 * np.pi * s["hour"] / 24)
    s["doy_sin"] = np.sin(2 * np.pi * t.dayofyear / 365.25)
    s["doy_cos"] = np.cos(2 * np.pi * t.dayofyear / 365.25)

    # Causal lags (shifted, so strictly past).
    for lag in (24, 48, SEASONAL_LAG):
        s[f"lag_{lag}"] = s[target].shift(lag)
    # Rolling means over past windows (shifted by 1 to exclude the current point).
    for win in (24, SEASONAL_LAG):
        s[f"roll_mean_{win}"] = s[target].shift(1).rolling(win).mean()
    return s


FEATURE_COLS = [
    "hour_sin", "hour_cos", "doy_sin", "doy_cos", "dow", "is_weekend", "month",
    "lag_24", "lag_48", f"lag_{SEASONAL_LAG}", "roll_mean_24", f"roll_mean_{SEASONAL_LAG}",
]


# --------------------------------------------------------------- baselines
def seasonal_naive(s: pd.DataFrame, target: str = "demand_mwh", lag: int = SEASONAL_LAG) -> pd.Series:
    """Forecast = value ``lag`` hours ago."""
    return s[target].shift(lag)


# --------------------------------------------------------------- quantile fit
@dataclass
class QuantileForecaster:
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    seed: int = 42
    models: dict = field(default_factory=dict)
    feature_cols: list[str] = field(default_factory=lambda: list(FEATURE_COLS))

    def fit(self, train: pd.DataFrame, target: str = "demand_mwh") -> "QuantileForecaster":
        if not HAS_SKLEARN:
            raise RuntimeError("sklearn required for QuantileForecaster; install .[prod]")
        # HistGradientBoostingRegressor: faster and better-regularized than the
        # classic GBM, so added features (e.g. weather) don't overfit noisy folds.
        from sklearn.ensemble import HistGradientBoostingRegressor

        tr = train.dropna(subset=self.feature_cols + [target])
        X, y = tr[self.feature_cols].to_numpy(), tr[target].to_numpy()
        for q in self.quantiles:
            m = HistGradientBoostingRegressor(
                loss="quantile", quantile=q, max_iter=300, learning_rate=0.05,
                max_depth=6, l2_regularization=1.0, early_stopping=True,
                validation_fraction=0.1, random_state=self.seed,
            )
            m.fit(X, y)
            self.models[q] = m
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.feature_cols].to_numpy()
        out = pd.DataFrame(index=df.index)
        for q, m in self.models.items():
            out[f"q{q}"] = m.predict(X)
        # Enforce monotone non-decreasing quantiles across the sorted levels.
        qs = sorted(self.models)
        arr = np.maximum.accumulate(out[[f"q{q}" for q in qs]].to_numpy(), axis=1)
        for i, q in enumerate(qs):
            out[f"q{q}"] = arr[:, i]
        return out


# --------------------------------------------------------------- metrics
def pinball_loss(y: np.ndarray, yhat: np.ndarray, q: float) -> float:
    d = y - yhat
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def _metrics(y: np.ndarray, yhat: np.ndarray) -> dict:
    err = y - yhat
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mape": float(np.mean(np.abs(err) / np.clip(np.abs(y), 1e-6, None)) * 100),
    }


# --------------------------------------------------------------- backtest
def rolling_origin_backtest(
    series: pd.DataFrame,
    target: str = "demand_mwh",
    n_folds: int = 4,
    horizon: int = 24,
    min_train: int = 24 * 30,
    extra_features: list[str] | None = None,
) -> dict:
    """Expanding-window backtest comparing the model to seasonal-naive.

    ``extra_features`` (e.g. weather columns already present on ``series``) are
    added to the feature set, enabling a like-for-like skill comparison.
    Returns aggregate metrics and per-fold detail. Falls back to the naive-only
    report if sklearn is unavailable.
    """
    feature_cols = list(FEATURE_COLS) + list(extra_features or [])
    s = make_features(series, target).dropna(subset=[target]).reset_index(drop=True)
    n = len(s)
    if n < min_train + horizon * n_folds:
        min_train = max(48, n - horizon * n_folds)
    folds = []
    naive_metrics, model_metrics = [], []
    for k in range(n_folds):
        test_end = n - (n_folds - 1 - k) * horizon
        test_start = test_end - horizon
        if test_start <= min_train:
            continue
        train = s.iloc[:test_start]
        test = s.iloc[test_start:test_end]
        y = test[target].to_numpy()

        naive = seasonal_naive(s)[test.index].to_numpy()
        nm = _metrics(y[~np.isnan(naive)], naive[~np.isnan(naive)]) if np.isfinite(naive).any() else {}
        naive_metrics.append(nm)

        fold = {"fold": k, "test_start": str(s["period"].iloc[test_start]), "naive": nm}
        if HAS_SKLEARN:
            # Hold out the tail of train as a conformal calibration set (CQR).
            n_cal = min(len(train) // 5, max(horizon * 2, 168))
            fit_df, cal_df = train.iloc[:-n_cal], train.iloc[-n_cal:]
            qf = QuantileForecaster(feature_cols=feature_cols).fit(fit_df, target)
            pred = qf.predict(test)
            lo, mid, hi = pred["q0.1"].to_numpy(), pred["q0.5"].to_numpy(), pred["q0.9"].to_numpy()

            mm = _metrics(y, mid)
            mm["pinball_0.5"] = pinball_loss(y, mid, 0.5)
            mm["coverage_80_raw"] = float(np.mean((y >= lo) & (y <= hi)))

            # CQR: calibrate the 80% band on the held-out calibration set.
            cal_df = cal_df.dropna(subset=feature_cols + [target])
            if len(cal_df):
                cp = qf.predict(cal_df)
                offset = cqr_calibrate(cp["q0.1"].to_numpy(), cp["q0.9"].to_numpy(),
                                       cal_df[target].to_numpy(), alpha=0.2)
                mm["coverage_80"] = float(np.mean((y >= lo - offset) & (y <= hi + offset)))
            else:
                mm["coverage_80"] = mm["coverage_80_raw"]
            model_metrics.append(mm)
            fold["model"] = mm
        folds.append(fold)

    def _avg(ms, key):
        vals = [m[key] for m in ms if key in m and np.isfinite(m[key])]
        return float(np.mean(vals)) if vals else float("nan")

    return {
        "n_folds": len(folds),
        "horizon": horizon,
        "naive_mae": _avg(naive_metrics, "mae"),
        "model_mae": _avg(model_metrics, "mae"),
        "model_rmse": _avg(model_metrics, "rmse"),
        "model_coverage_80": _avg(model_metrics, "coverage_80"),
        "model_coverage_80_raw": _avg(model_metrics, "coverage_80_raw"),
        "skill_vs_naive": (
            1 - _avg(model_metrics, "mae") / _avg(naive_metrics, "mae")
            if model_metrics and np.isfinite(_avg(naive_metrics, "mae")) else float("nan")
        ),
        "folds": folds,
    }


# --------------------------------------------------------------- conformal
def cqr_calibrate(
    cal_lower: np.ndarray, cal_upper: np.ndarray, cal_y: np.ndarray, alpha: float = 0.2
) -> float:
    """CQR conformity offset for target coverage 1-alpha (Romano et al. 2019).

    Returns the amount to widen [lower, upper] symmetrically so that empirical
    coverage on unseen data meets 1-alpha in finite samples.
    """
    scores = np.maximum(cal_lower - cal_y, cal_y - cal_upper)
    n = len(scores)
    level = np.ceil((n + 1) * (1 - alpha)) / n
    level = min(level, 1.0)
    return float(np.quantile(scores, level, method="higher"))
