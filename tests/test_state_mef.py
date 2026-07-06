import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from gridpulse import state_mef  # noqa: E402


def _regime_w(n=3000, seed=0):
    """Per-hour frame with a planted 2-regime MEF: gas regime 400, coal regime 900."""
    rng = np.random.default_rng(seed)
    state = np.zeros(n, int)
    for t in range(1, n):
        state[t] = state[t - 1] if rng.random() < 0.98 else 1 - state[t - 1]
    mef = np.where(state == 0, 400.0, 900.0)
    x1 = np.clip(3000 + 1500 * np.sin(np.arange(n) / 10) + rng.normal(0, 300, n), 0, None)  # non-renew
    x2 = np.clip(1000 + 800 * np.cos(np.arange(n) / 7) + rng.normal(0, 200, n), 0, None)    # renewable
    co2 = np.zeros(n)
    for t in range(1, n):
        co2[t] = 5000 + 0.3 * co2[t - 1] + mef[t] * x1[t] + rng.normal(0, 2000)
    periods = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({"period": periods.astype(str), "ba": "T",
                         "co2_kg": co2, "gen_mwh": x1 + x2, "WND": x2})


def test_state_ar_mef_recovers_planted_regimes():
    r = state_mef.state_ar_mef(_regime_w(), search_reps=8, min_obs=500, seed=1)
    assert r is not None
    # two distinct regime MEFs recovered near the planted 400 / 900
    assert abs(r["mef_low_regime"] - 400) < 70
    assert abs(r["mef_high_regime"] - 900) < 100
    assert r["regime_spread_pct"] > 50          # a genuinely state-dependent margin
    assert 0.0 <= r["pi_low"] <= 1.0 and abs(r["pi_low"] + r["pi_high"] - 1.0) < 1e-6


def test_state_ar_mef_insufficient_data_returns_none():
    w = _regime_w(n=100)
    assert state_mef.state_ar_mef(w, min_obs=500) is None


def test_convergence_count():
    df = pd.DataFrame({
        "ba": ["A", "B", "C"],
        "m1": [100.0, 100.0, 50.0],
        "m2": [110.0, 300.0, np.nan],   # C has only 1 estimate -> not evaluable
        "m3": [105.0, 500.0, np.nan],
    })
    conv, evald = state_mef.convergence_count(df, ["m1", "m2", "m3"], tol_pct=20)
    assert (conv, evald) == (1, 2)      # A converges (100-110), B does not; C skipped
