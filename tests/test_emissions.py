import numpy as np
import pandas as pd

from gridpulse import emissions as em
from gridpulse.regions import factor_for
from gridpulse.synthetic import make_fixture, planted_mef


def _single_ba_series(n=400, base_clean=5000.0, marg_factor_fuel="NG", seed=0):
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2024-01-01", periods=n, freq="h")
    marg = np.clip(3000 + 2000 * np.sin(np.arange(n) / 12) + rng.normal(0, 150, n), 0, None)
    rows = []
    for t, g in zip(periods, marg):
        rows.append({"period": t.isoformat(), "ba": "T", "fueltype": "NUC", "mwh": base_clean})
        rows.append({"period": t.isoformat(), "ba": "T", "fueltype": marg_factor_fuel, "mwh": float(g)})
    return pd.DataFrame(rows)


def test_hourly_co2_columns_and_fossil():
    fuel = _single_ba_series(50)
    hc = em.hourly_co2(fuel)
    assert set(["ba", "period", "co2_kg", "gen_mwh", "fossil_mwh"]).issubset(hc.columns)
    # NUC contributes 0 on production basis; only NG (fossil) emits.
    assert (hc["fossil_mwh"] <= hc["gen_mwh"]).all()
    assert hc["co2_kg"].min() >= 0


def test_aef_between_zero_and_dirtiest_factor():
    fuel = _single_ba_series(200)
    hc = em.hourly_co2(fuel)
    aef = em.aef_by_ba(hc)
    v = float(aef["aef_kg_per_mwh"].iloc[0])
    assert 0 < v < factor_for("NG")  # blended clean + gas < pure gas


def test_mef_recovers_planted_ground_truth_machine_precision():
    fuel = _single_ba_series(500, marg_factor_fuel="NG")
    hc = em.hourly_co2(fuel)
    dem = hc[["period", "ba", "gen_mwh"]].rename(columns={"gen_mwh": "demand_mwh"})
    asm = hc.merge(dem, on=["ba", "period"])
    res = em.siler_evans_mef(asm.assign(ba="T"), driver="demand", n_boot=200)
    assert res is not None
    assert abs(res.mef_kg_per_mwh - factor_for("NG")) < 1e-9
    assert res.r2 > 0.999


def test_mef_bootstrap_ci_brackets_estimate():
    fuel = _single_ba_series(500, seed=3)
    hc = em.hourly_co2(fuel)
    dem = hc[["period", "ba", "gen_mwh"]].rename(columns={"gen_mwh": "demand_mwh"})
    asm = hc.merge(dem, on=["ba", "period"])
    res = em.siler_evans_mef(asm.assign(ba="T"), driver="demand", n_boot=500)
    assert res.ci_low <= res.mef_kg_per_mwh <= res.ci_high


def test_mef_coal_margin_higher_than_gas_margin():
    gas = _single_ba_series(400, marg_factor_fuel="NG")
    coal = _single_ba_series(400, marg_factor_fuel="COL")
    def mef(fuel):
        hc = em.hourly_co2(fuel)
        dem = hc[["period", "ba", "gen_mwh"]].rename(columns={"gen_mwh": "demand_mwh"})
        asm = hc.merge(dem, on=["ba", "period"])
        return em.siler_evans_mef(asm.assign(ba="T"), driver="demand", n_boot=50).mef_kg_per_mwh
    assert mef(coal) > mef(gas)


def test_assemble_and_mef_by_ba_over_fixture():
    fuel_long, demand_long = make_fixture(hours=24 * 30)
    asm = em.assemble_hourly(fuel_long, demand_long)
    mef = em.mef_by_ba(asm, driver="demand", n_boot=100)
    assert len(mef) == 4
    # planted marginal intensities recovered closely on noisy synthetic data
    for _, r in mef.iterrows():
        assert abs(r["mef_kg_per_mwh"] - planted_mef(r["ba"])) / planted_mef(r["ba"]) < 0.05


def test_empty_inputs_are_safe():
    assert em.hourly_co2(pd.DataFrame()).empty
    assert em.aef_by_ba(pd.DataFrame()).empty
