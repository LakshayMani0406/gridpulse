"""Thrust 1: short-run vs long-run marginal carbon.

Two parts:

A. **Holland reproduction** (Holland, Kotchen, Mansur & Yates 2022, PNAS
   doi:10.1073/pnas.2116632119). Over 2019->present, has each BA's *marginal*
   emission factor fallen as fast as its *average*? If marginal is sticky while
   average declines (renewables cut the average but gas still sets the margin),
   the short-run siting signal ages differently than people assume.

B. **LRMER vs short-run MEF.** A data center lives 15+ years, so its true impact
   is long-run (it induces new capacity), not the short-run dispatch margin.
   Compare siting ranks under short-run MEF (ours) vs NREL Cambium long-run
   marginal emission rates (LRMER). Report rank flips + MtCO2/yr divergence.
   (Cambium loader lives in `cambium.py`.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .emissions import _ols, aef_by_ba, assemble_hourly, mef_by_ba


def annual_factors(fuel_long: pd.DataFrame, demand_long: pd.DataFrame,
                   min_hours: int = 24 * 60) -> pd.DataFrame:
    """Per (ba, year): AEF and short-run MEF, for BA-years with enough data."""
    asm = assemble_hourly(fuel_long, demand_long)
    asm["year"] = pd.to_datetime(asm["period"]).dt.year
    rows = []
    for (ba, yr), g in asm.groupby(["ba", "year"]):
        if len(g) < min_hours:
            continue
        aef = aef_by_ba(g)
        mef = mef_by_ba(g.assign(ba=ba), driver="demand", n_boot=100)
        if aef.empty or mef.empty:
            continue
        rows.append({"ba": ba, "year": int(yr),
                     "aef": float(aef["aef_kg_per_mwh"].iloc[0]),
                     "mef": float(mef["mef_kg_per_mwh"].iloc[0]),
                     "hours": len(g)})
    return pd.DataFrame(rows)


def holland_test(annual: pd.DataFrame, min_years: int = 4) -> pd.DataFrame:
    """Per BA: linear trend (kg/MWh per year) in AEF vs MEF over years.

    Returns slopes and the marginal/average trend ratio. Ratio << 1 means the
    marginal factor is 'sticky' relative to a falling average (the Holland finding).
    """
    out = []
    for ba, g in annual.groupby("ba"):
        g = g.sort_values("year")
        if g["year"].nunique() < min_years:
            continue
        x = g["year"].to_numpy(float)
        aef_slope, _, aef_r2 = _ols(x, g["aef"].to_numpy(float))
        mef_slope, _, mef_r2 = _ols(x, g["mef"].to_numpy(float))
        out.append({"ba": ba, "n_years": g["year"].nunique(),
                    "aef_trend_per_yr": aef_slope, "mef_trend_per_yr": mef_slope,
                    "aef_r2": aef_r2, "mef_r2": mef_r2,
                    "marginal_stickiness": (mef_slope / aef_slope) if aef_slope else np.nan,
                    "aef_first": float(g["aef"].iloc[0]), "aef_last": float(g["aef"].iloc[-1]),
                    "mef_first": float(g["mef"].iloc[0]), "mef_last": float(g["mef"].iloc[-1])})
    return pd.DataFrame(out)


def lrmer_vs_mef(short_run_mef: pd.Series, lrmer: pd.Series, load_mw: float = 100.0) -> pd.DataFrame:
    """Rank BAs under short-run MEF vs long-run LRMER; flag flips + CO2 divergence."""
    df = pd.DataFrame({"mef_short_run": short_run_mef, "lrmer_long_run": lrmer}).dropna()
    if df.empty:
        return df
    df["rank_short_run"] = df["mef_short_run"].rank(method="min").astype(int)
    df["rank_long_run"] = df["lrmer_long_run"].rank(method="min").astype(int)
    df["rank_shift"] = df["rank_short_run"] - df["rank_long_run"]
    hours = 8760.0
    df["annual_kt_short"] = load_mw * hours * df["mef_short_run"] / 1e6
    df["annual_kt_long"] = load_mw * hours * df["lrmer_long_run"] / 1e6
    df["divergence_kt"] = df["annual_kt_long"] - df["annual_kt_short"]
    return df.sort_values("lrmer_long_run").reset_index().rename(columns={"index": "ba"})
