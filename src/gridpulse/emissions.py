"""Emission factors: average (AEF) and marginal (MEF, Siler-Evans).

Average emission factor (AEF)
    Total CO2 emitted divided by total generation over a window -- what a naive
    analysis attributes to *any* MWh consumed.

Marginal emission factor (MEF, Siler-Evans et al. 2012)
    The CO2 impact of one *additional* MWh. Estimated by regressing the hour-to-
    hour change in emissions on the change in a driver (demand or generation).
    A new data center is an increment of load, so its climate impact is set by
    the MEF, not the AEF -- and the two can rank regions differently.

Ref: Siler-Evans, Azevedo & Morgan (2012), Environ. Sci. Technol.,
     doi:10.1021/es300145v.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .regions import FOSSIL_FUELS, factor_for

log = logging.getLogger("gridpulse.emissions")


# ------------------------------------------------------------------ hourly CO2
def hourly_co2(fuel_long: pd.DataFrame) -> pd.DataFrame:
    """From tidy fuel-mix rows -> per (ba, period): co2_kg, gen_mwh, fossil_mwh.

    Expects columns: period, ba, fueltype, mwh. Negative generation values
    (occasionally reported for storage/other) are floored at 0 for CO2.
    """
    if fuel_long.empty:
        return pd.DataFrame(columns=["ba", "period", "co2_kg", "gen_mwh", "fossil_mwh"])
    df = fuel_long.rename(columns={"mwh": "mwh"}).copy()
    df["mwh"] = pd.to_numeric(df["mwh"], errors="coerce").fillna(0.0)
    df["factor"] = df["fueltype"].map(factor_for)
    df["co2_kg"] = df["mwh"].clip(lower=0) * df["factor"]
    df["is_fossil"] = df["fueltype"].str.upper().isin(FOSSIL_FUELS)
    df["fossil_mwh"] = np.where(df["is_fossil"], df["mwh"].clip(lower=0), 0.0)

    g = df.groupby(["ba", "period"], as_index=False).agg(
        co2_kg=("co2_kg", "sum"),
        gen_mwh=("mwh", lambda s: s.clip(lower=0).sum()),
        fossil_mwh=("fossil_mwh", "sum"),
    )
    return g


# ------------------------------------------------------------------------ AEF
def aef_by_ba(hourly: pd.DataFrame) -> pd.DataFrame:
    """Average emission factor per BA = sum(co2) / sum(generation), kg/MWh."""
    if hourly.empty:
        return pd.DataFrame(columns=["ba", "aef_kg_per_mwh", "total_co2_t", "total_gen_mwh", "hours"])
    g = hourly.groupby("ba", as_index=False).agg(
        total_co2_kg=("co2_kg", "sum"),
        total_gen_mwh=("gen_mwh", "sum"),
        hours=("period", "nunique"),
    )
    g["aef_kg_per_mwh"] = g["total_co2_kg"] / g["total_gen_mwh"].replace(0, np.nan)
    g["total_co2_t"] = g["total_co2_kg"] / 1000.0
    return g[["ba", "aef_kg_per_mwh", "total_co2_t", "total_gen_mwh", "hours"]]


# ------------------------------------------------------------------------ MEF
@dataclass
class MEFResult:
    ba: str
    mef_kg_per_mwh: float
    ci_low: float
    ci_high: float
    intercept: float
    r2: float
    n_pairs: int
    driver: str


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """OLS y = a + b x. Returns (slope, intercept, r2)."""
    n = len(x)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    xm, ym = x.mean(), y.mean()
    sxx = np.sum((x - xm) ** 2)
    if sxx == 0:
        return float("nan"), float("nan"), float("nan")
    b = np.sum((x - xm) * (y - ym)) / sxx
    a = ym - b * xm
    yhat = a + b * x
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - ym) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(b), float(a), float(r2)


def siler_evans_mef(
    series: pd.DataFrame,
    driver: str = "demand",
    n_boot: int = 1000,
    ci: float = 0.95,
    min_delta: float = 0.0,
    seed: int = 42,
) -> MEFResult | None:
    """Estimate one BA's MEF by regressing ΔCO2 on Δ(driver) over consecutive hours.

    Parameters
    ----------
    series : per-hour rows for a single BA with columns ``period``, ``co2_kg``,
        and the driver column (``demand_mwh`` or ``gen_mwh``/``fossil_mwh``).
    driver : which column drives the margin. ``"demand"`` -> ``demand_mwh``
        (siting-relevant); ``"generation"`` -> ``gen_mwh``; ``"fossil"`` ->
        ``fossil_mwh``.
    """
    col = {"demand": "demand_mwh", "generation": "gen_mwh", "fossil": "fossil_mwh"}[driver]
    s = series.sort_values("period").reset_index(drop=True)
    if col not in s.columns or len(s) < 3:
        return None
    # Consecutive-hour first differences.
    dt = pd.to_datetime(s["period"]).diff()
    consecutive = dt == pd.Timedelta(hours=1)
    dco2 = s["co2_kg"].diff()
    ddrv = s[col].diff()
    mask = consecutive & dco2.notna() & ddrv.notna() & (ddrv.abs() > min_delta)
    x = ddrv[mask].to_numpy(dtype=float)
    y = dco2[mask].to_numpy(dtype=float)
    if len(x) < 3:
        return None

    slope, intercept, r2 = _ols(x, y)

    rng = np.random.default_rng(seed)
    n = len(x)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        b, _, _ = _ols(x[idx], y[idx])
        boots[i] = b
    lo = float(np.nanpercentile(boots, (1 - ci) / 2 * 100))
    hi = float(np.nanpercentile(boots, (1 + ci) / 2 * 100))

    ba = str(series["ba"].iloc[0]) if "ba" in series.columns else "?"
    return MEFResult(ba, float(slope), lo, hi, float(intercept), float(r2), n, driver)


def mef_by_ba(assembled: pd.DataFrame, driver: str = "demand", **kw) -> pd.DataFrame:
    """Run the Siler-Evans MEF per BA over an assembled hourly frame."""
    out: list[dict] = []
    for ba, grp in assembled.groupby("ba"):
        res = siler_evans_mef(grp.assign(ba=ba), driver=driver, **kw)
        if res is None:
            continue
        out.append(vars(res))
    return pd.DataFrame(out)


# ------------------------------------------------------------------- assemble
def assemble_hourly(fuel_long: pd.DataFrame, demand_long: pd.DataFrame | None = None) -> pd.DataFrame:
    """Join CO2/generation with demand into one per-(ba,period) frame for MEF."""
    hc = hourly_co2(fuel_long)
    if demand_long is not None and not demand_long.empty:
        d = demand_long.rename(columns={"respondent": "ba", "value": "demand_mwh", "mwh": "demand_mwh"})
        keep = [c for c in ["period", "ba", "demand_mwh"] if c in d.columns]
        d = d[keep]
        hc = hc.merge(d, on=["ba", "period"], how="left")
    else:
        hc["demand_mwh"] = np.nan
    return hc
