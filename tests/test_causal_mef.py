import numpy as np
import pandas as pd

from gridpulse import causal_mef as cm
from gridpulse.regions import factor_for


def _synthetic_ba(n=1500, seed=0):
    """NUC baseload + gas filling residual; exogenous VRE ramps displace gas.
    VRE-ramp MEF must recover the gas factor (469)."""
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2024-01-01", periods=n, freq="h")
    demand = 8000 + 1500 * np.sin(np.arange(n) / 12) + rng.normal(0, 50, n)
    vre = np.clip(2500 + 2000 * np.sin(np.arange(n) / 6 + 1) + rng.normal(0, 400, n), 0, None)
    nuc = 3000.0
    gas = np.clip(demand - vre - nuc, 0, None)  # gas fills residual
    rows = []
    for t, d, v, g in zip(periods, demand, vre, gas):
        rows.append({"period": t.isoformat(), "ba": "T", "fueltype": "NUC", "mwh": nuc})
        rows.append({"period": t.isoformat(), "ba": "T", "fueltype": "SUN", "mwh": float(v)})
        rows.append({"period": t.isoformat(), "ba": "T", "fueltype": "NG", "mwh": float(g)})
    fuel = pd.DataFrame(rows)
    dem = pd.DataFrame({"period": [t.isoformat() for t in periods], "ba": "T", "mwh": demand})
    return fuel, dem


def test_vre_ramp_mef_recovers_gas_margin():
    fuel, dem = _synthetic_ba()
    w = cm._wide(fuel, dem, "T")
    res = cm.mef_from_vre_ramps(w, min_ramp_frac=0.01, max_demand_frac=0.05)
    assert res is not None
    # displaced carbon per MWh of solar ≈ gas factor
    assert abs(res["mef_vre"] - factor_for("NG")) / factor_for("NG") < 0.10
    assert res["ci_low"] <= res["mef_vre"] <= res["ci_high"]


def test_trip_detection_flags_injected_outage():
    fuel, dem = _synthetic_ba(n=800)
    w = cm._wide(fuel, dem, "T")
    # inject a coal column with a sharp mid-series drop (a trip)
    w["COL"] = 1000.0
    w.loc[400, "COL"] = 100.0  # sudden 900 MW drop
    w["fossil"] = w["fossil"] + w["COL"]
    trips = cm.detect_generation_trips(w, fuels=("COL",))
    assert not trips.empty
    assert (trips["fuel"] == "COL").any()


def test_triangulate_columns():
    fuel, dem = _synthetic_ba()
    t = cm.triangulate_mef(fuel, dem, ["T"])
    assert "mef_siler_evans" in t.columns and "mef_vre_ramp" in t.columns
    assert len(t) == 1
