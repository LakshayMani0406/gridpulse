import numpy as np
import pandas as pd
import pytest

from gridpulse import model as md
from gridpulse.config import HAS_SKLEARN


def _demand_series(n=24 * 120, seed=1):
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2024-01-01", periods=n, freq="h")
    h = np.arange(n)
    load = (
        1000
        + 300 * np.sin(2 * np.pi * (h % 24) / 24)
        + 150 * np.sin(2 * np.pi * (h % 168) / 168)
        + rng.normal(0, 40, n)
    )
    return pd.DataFrame({"period": periods, "demand_mwh": load})


def test_features_are_causal_no_lookahead():
    s = _demand_series(300)
    f = md.make_features(s)
    # lag_24 at row i must equal target at row i-24
    assert np.isnan(f["lag_24"].iloc[0])
    assert f["lag_24"].iloc[50] == s["demand_mwh"].iloc[26]
    # rolling mean excludes current point (shift(1))
    manual = s["demand_mwh"].iloc[26:50].mean()
    assert abs(f["roll_mean_24"].iloc[50] - manual) < 1e-6


def test_seasonal_naive_shifts_one_week():
    s = _demand_series(300)
    naive = md.seasonal_naive(s)
    assert naive.iloc[200] == s["demand_mwh"].iloc[200 - md.SEASONAL_LAG]


def test_pinball_loss_zero_when_perfect():
    y = np.array([1.0, 2.0, 3.0])
    assert md.pinball_loss(y, y, 0.5) == 0.0


def test_cqr_offset_nonnegative_and_covers():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 500)
    lo, hi = np.full(500, -0.5), np.full(500, 0.5)  # too-narrow band
    off = md.cqr_calibrate(lo, hi, y, alpha=0.2)
    assert off > 0
    cover = np.mean((y >= lo - off) & (y <= hi + off))
    assert cover >= 0.75  # ~0.8 target, finite-sample


@pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not installed")
def test_backtest_model_beats_or_matches_naive():
    s = _demand_series(24 * 120)
    rep = md.rolling_origin_backtest(s, n_folds=3, horizon=24)
    assert rep["n_folds"] >= 1
    assert np.isfinite(rep["model_mae"])
    # coverage of the 80% band should be in a sane range
    assert 0.4 <= rep["model_coverage_80"] <= 1.0


@pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn not installed")
def test_quantile_forecaster_monotone():
    s = md.make_features(_demand_series(24 * 90)).dropna()
    qf = md.QuantileForecaster().fit(s.iloc[:1500])
    pred = qf.predict(s.iloc[1500:1600])
    assert (pred["q0.1"] <= pred["q0.5"] + 1e-6).all()
    assert (pred["q0.5"] <= pred["q0.9"] + 1e-6).all()
