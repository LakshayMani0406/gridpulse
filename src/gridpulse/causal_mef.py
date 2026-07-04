"""Thrust 3: validate the marginal emission factor with supply-side instruments.

The MEF has no published ground truth (unlike the AEF, which EIA publishes). So
instead of trusting one demand-driven regression (Siler-Evans), we identify the
margin from *exogenous supply* variation and triangulate:

1. **Siler-Evans** (baseline): ΔCO2 regressed on Δdemand (demand-driven).
2. **VRE-ramp instrument** (Ricks et al. / IOP 2024): when wind+solar ramp for
   weather reasons and demand is ~flat, fossil backs off. The carbon displaced
   per extra MWh of VRE equals the marginal fossil emission rate:
   MEF = -d(CO2)/d(VRE).
3. **Generation-trip instrument**: a sudden large drop in a dispatchable fuel
   while demand is not falling is a quasi-random supply shock; the emissions
   response per lost MWh reveals the replacement margin.

Convergence across independent identifications is real validation; divergence is
itself a finding. Ref: Ricks, Xu & Jenkins, "Minimizing emissions from grid-based
hydrogen..." and the LME validation paper (Environ. Res.: Energy, 2024,
doi:10.1088/2753-3751/ad72f6). Clustered inference: Bertrand, Duflo & Mullainathan
(2004), QJE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .emissions import _ols, hourly_co2, siler_evans_mef
from .regions import CLEAN_FUELS, FOSSIL_FUELS

VRE_FUELS = ("SUN", "WND")


def _wide(fuel_long: pd.DataFrame, demand_long: pd.DataFrame, ba: str) -> pd.DataFrame:
    """Per-hour frame for one BA: co2, demand, vre, fossil, and each fuel."""
    f = fuel_long[fuel_long["ba"] == ba].copy()
    if f.empty:
        return pd.DataFrame()
    f["mwh"] = pd.to_numeric(f["mwh"], errors="coerce").fillna(0.0).clip(lower=0)
    wide = f.pivot_table(index="period", columns="fueltype", values="mwh",
                         aggfunc="sum", fill_value=0.0)
    hc = hourly_co2(f).set_index("period")[["co2_kg", "gen_mwh"]]
    wide = wide.join(hc)
    wide["vre"] = sum(wide[c] for c in VRE_FUELS if c in wide.columns)
    wide["fossil"] = sum(wide[c] for c in FOSSIL_FUELS if c in wide.columns)
    wide["clean"] = sum(wide[c] for c in CLEAN_FUELS if c in wide.columns)
    d = demand_long[demand_long["ba"] == ba][["period", "mwh"]].rename(columns={"mwh": "demand"})
    wide = wide.join(d.set_index("period"))
    wide = wide.reset_index()
    wide["period"] = pd.to_datetime(wide["period"])
    return wide.sort_values("period").reset_index(drop=True)


def _consecutive_diffs(w: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    dt = w["period"].diff()
    d = w[cols].diff()
    d["consec"] = dt == pd.Timedelta(hours=1)
    return d


def mef_from_vre_ramps(w: pd.DataFrame, min_ramp_frac: float = 0.02,
                       max_demand_frac: float = 0.02, n_boot: int = 500,
                       seed: int = 42) -> dict | None:
    """MEF = -slope of ΔCO2 on ΔVRE, on hours with large VRE ramps & flat demand.

    Restricting to |ΔVRE| large and |Δdemand| small isolates weather-driven
    (exogenous) supply variation from demand-driven dispatch.
    """
    if w.empty or "vre" not in w or w["vre"].sum() == 0:
        return None
    d = _consecutive_diffs(w, ["co2_kg", "vre", "demand"])
    scale = w["demand"].median() or 1.0
    mask = (d["consec"] & d["co2_kg"].notna() & d["vre"].notna() & d["demand"].notna()
            & (d["vre"].abs() > min_ramp_frac * scale)
            & (d["demand"].abs() < max_demand_frac * scale))
    x = d.loc[mask, "vre"].to_numpy(float)
    y = d.loc[mask, "co2_kg"].to_numpy(float)
    if len(x) < 100:  # need enough exogenous ramps for a stable estimate
        return None
    slope, _, r2 = _ols(x, y)
    rng = np.random.default_rng(seed)
    boots = np.array([_ols(x[i], y[i])[0] for i in
                      (rng.integers(0, len(x), len(x)) for _ in range(n_boot))])
    mef = -slope
    lo, hi = -np.nanpercentile(boots, 97.5), -np.nanpercentile(boots, 2.5)
    return {"mef_vre": float(mef), "ci_low": float(lo), "ci_high": float(hi),
            "r2": float(r2), "n": int(len(x))}


def detect_generation_trips(w: pd.DataFrame, fuels=("COL", "NG", "NUC"),
                            drop_z: float = 4.0, min_drop_frac: float = 0.03) -> pd.DataFrame:
    """Flag hours where a dispatchable fuel drops sharply while demand is not falling.

    A large sudden drop in COL/NG/NUC that is not load-following (demand flat or
    up) is a quasi-random supply shock (a forced outage / trip).
    """
    present = [f for f in fuels if f in w.columns]
    if w.empty or not present:
        return pd.DataFrame()
    d = _consecutive_diffs(w, present + ["demand", "co2_kg"])
    scale = w["demand"].median() or 1.0
    events = []
    for f in present:
        df_ = d[f]
        sd = df_.std() or 1.0
        trip = (d["consec"] & (df_ < -drop_z * sd) & (df_ < -min_drop_frac * scale)
                & (d["demand"] > -0.01 * scale))
        for idx in w.index[trip.fillna(False)]:
            events.append({"period": w.loc[idx, "period"], "fuel": f,
                           "drop_mwh": float(-d.loc[idx, f]),
                           "d_demand": float(d.loc[idx, "demand"]),
                           "d_co2_kg": float(d.loc[idx, "co2_kg"])})
    return pd.DataFrame(events)


def mef_from_outages(w: pd.DataFrame, **kw) -> dict | None:
    """MEF implied by the emissions response to detected supply trips.

    At a trip, lost generation ΔG (from the tripped fuel) is replaced by other
    units at the same demand; the net ΔCO2 / (−ΔG_load-served) approximates the
    marginal rate of the replacement. We regress ΔCO2 on Δ(non-tripped fossil)
    over trip hours.
    """
    trips = detect_generation_trips(w, **kw)
    if trips.empty or len(trips) < 15:
        return None
    # marginal replacement rate: emissions change per MWh of net generation change
    # excluding the tripped fuel's own drop (i.e., what ramped to cover it)
    d = _consecutive_diffs(w, ["co2_kg", "fossil", "vre", "clean", "demand"])
    idx = w.index[w["period"].isin(set(trips["period"]))]
    # replacement generation = Δdemand - Δvre - Δclean (what fossil had to do net)
    repl = (d.loc[idx, "demand"] - d.loc[idx, "vre"]).to_numpy(float)
    y = d.loc[idx, "co2_kg"].to_numpy(float)
    m = np.isfinite(repl) & np.isfinite(y) & (np.abs(repl) > 1e-6)
    if m.sum() < 15:
        return None
    slope, _, r2 = _ols(repl[m], y[m])
    return {"mef_outage": float(slope), "r2": float(r2), "n_trips": int(len(trips)),
            "n_used": int(m.sum())}


def triangulate_mef(fuel_long: pd.DataFrame, demand_long: pd.DataFrame,
                    bas: list[str]) -> pd.DataFrame:
    """Per-BA table of independent MEF estimates and their spread."""
    rows = []
    for ba in bas:
        w = _wide(fuel_long, demand_long, ba)
        if w.empty or len(w) < 200:
            continue
        se = siler_evans_mef(
            w.rename(columns={"demand": "demand_mwh"}).assign(ba=ba),
            driver="demand", n_boot=200)
        vre = mef_from_vre_ramps(w)
        outg = mef_from_outages(w)
        est = {"ba": ba,
               "mef_siler_evans": se.mef_kg_per_mwh if se else np.nan,
               "mef_vre_ramp": vre["mef_vre"] if vre else np.nan,
               "mef_outage": outg["mef_outage"] if outg else np.nan,
               "n_vre": vre["n"] if vre else 0,
               "n_trips": outg["n_trips"] if outg else 0}
        vals = np.array([est["mef_siler_evans"], est["mef_vre_ramp"], est["mef_outage"]], float)
        vals = vals[np.isfinite(vals)]
        if len(vals) >= 2:
            est["mef_mean"] = float(np.mean(vals))
            est["mef_spread_pct"] = float(100 * (np.max(vals) - np.min(vals)) / np.mean(vals)) \
                if np.mean(vals) else np.nan
        rows.append(est)
    return pd.DataFrame(rows)
