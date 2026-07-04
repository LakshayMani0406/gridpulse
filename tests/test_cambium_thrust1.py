import numpy as np
import pandas as pd

from gridpulse import cambium
from gridpulse.regions import REGION_CODES
from gridpulse.thrust1 import annual_factors, holland_test, lrmer_vs_mef


def test_crosswalk_covers_all_bas():
    # every modeled BA maps to at least one Cambium GEA region
    for ba in REGION_CODES:
        assert ba in cambium.BA_TO_GEA
        assert len(cambium.BA_TO_GEA[ba]) >= 1


def test_value_col_finds_lrmer():
    df = pd.DataFrame({"gea": ["CAISO"], "t": [2025], "lrmer_co2e": [300.0], "other": [1]})
    assert cambium._value_col(df) == "lrmer_co2e"


def test_lrmer_vs_mef_flags_flips():
    # hydro BA: greenest short-run (near-zero margin) but long-run LRMER exceeds
    # the gas BA (new load induces fossil capacity) -> rank flip
    mef = pd.Series({"HYDRO": 10.0, "GAS": 400.0, "COAL": 900.0})
    lrmer = pd.Series({"HYDRO": 380.0, "GAS": 350.0, "COAL": 800.0})
    out = lrmer_vs_mef(mef, lrmer)
    hydro = out[out["ba"] == "HYDRO"].iloc[0]
    # greenest short-run (rank 1) but not greenest long-run -> positive shift
    assert hydro["rank_short_run"] == 1
    assert hydro["rank_long_run"] > 1
    assert hydro["rank_shift"] < 0  # short_run rank - long_run rank


def test_annual_factors_and_holland():
    # two years, AEF falling faster than MEF (marginal 'sticky')
    rows, dem = [], []
    for yr, aef_gas in [(2023, 4000.0), (2024, 2000.0)]:  # more gas in 2023
        periods = pd.date_range(f"{yr}-01-01", periods=24 * 65, freq="h")
        rng = np.random.default_rng(yr)
        for i, t in enumerate(periods):
            gas = aef_gas + 1500 * np.sin(i / 12) + rng.normal(0, 40)
            rows.append({"period": t.isoformat(), "ba": "Z", "fueltype": "NG", "mwh": max(gas, 0)})
            rows.append({"period": t.isoformat(), "ba": "Z", "fueltype": "WND", "mwh": 3000.0})
            dem.append({"period": t.isoformat(), "ba": "Z", "mwh": max(gas, 0) + 3000.0})
    ann = annual_factors(pd.DataFrame(rows), pd.DataFrame(dem), min_hours=24 * 60)
    assert set(ann["year"]) == {2023, 2024}
    hol = holland_test(ann, min_years=2)
    assert not hol.empty and "marginal_stickiness" in hol.columns
