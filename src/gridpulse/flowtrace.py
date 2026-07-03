"""Consumption-based (import-adjusted) emissions via interchange flow-tracing.

Production-based emissions credit a BA only for what it generates. But a data
center in BA A drawing dirty imports from BA B should be charged for those
imports. Flow-tracing solves the network so each BA's *consumption* emission
rate reflects its own generation plus the emissions embodied in net imports.

Method: de Chalendar, Taggart & Azevedo (2019), PNAS, doi:10.1073/pnas.1912950116.
The per-hour linear system is adapted from the reference implementation
``jdechalendar/gridemissions`` (``consumption_emissions``):

    f_i^c * (P_i + Imp_i) - sum_j Imp_ij * f_j^c = F_i^p

where f^c is the consumption emission rate, P production, Imp the import matrix,
and F^p production emissions. Solving for f^c routes emissions along trade.
"""
from __future__ import annotations

import logging
import sys

import numpy as np
import pandas as pd

from .emissions import hourly_co2, siler_evans_mef

log = logging.getLogger("gridpulse.flowtrace")


def solve_consumption_rates(F: np.ndarray, P: np.ndarray, ID: np.ndarray) -> np.ndarray:
    """Solve one hour's consumption emission rates (kg/MWh).

    Parameters
    ----------
    F : production emissions per BA (kg/hr).
    P : production (generation) per BA (MWh/hr).
    ID : signed interchange matrix, exports positive: ``ID[i, j]`` = flow from i to j.
    Adapted from de Chalendar's ``gridemissions.emissions.consumption_emissions``.
    """
    Imp = (-ID).clip(min=0)          # imports = negative exports
    I_tot = Imp.sum(axis=1)          # total imports into each node
    A = np.diag(P + I_tot) - Imp
    b = F.astype(float).copy()

    # Handle isolated / zero nodes so the system stays well-posed.
    if np.linalg.cond(A) > (1.0 / sys.float_info.epsilon):
        for i in range(len(A)):
            if (np.abs(A[:, i]).sum() == 0.0) and (np.abs(A[i, :]).sum() == 0.0):
                A[i, i] = 1.0
                b[i] = 0.0
    try:
        x = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        x = np.linalg.lstsq(A, b, rcond=None)[0]
    return x


def build_hourly_inputs(
    fuel_long: pd.DataFrame,
    interchange: pd.DataFrame,
    bas: list[str],
) -> dict[str, dict]:
    """Assemble per-period F (prod emissions), P (generation), ID (trade matrix)."""
    hc = hourly_co2(fuel_long)
    hc = hc[hc["ba"].isin(bas)]
    idx = {ba: i for i, ba in enumerate(bas)}

    ix = interchange.rename(columns={"from_ba": "from_ba", "to_ba": "to_ba"}).copy()
    ix = ix[ix["from_ba"].isin(bas) & ix["to_ba"].isin(bas)]
    ix["mwh"] = pd.to_numeric(ix["mwh"], errors="coerce").fillna(0.0)

    out: dict[str, dict] = {}
    for period, grp in hc.groupby("period"):
        n = len(bas)
        F = np.zeros(n)
        P = np.zeros(n)
        for _, r in grp.iterrows():
            i = idx[r["ba"]]
            F[i] = r["co2_kg"]
            P[i] = r["gen_mwh"]
        out[period] = {"F": F, "P": P, "ID": np.zeros((n, n))}

    for period, grp in ix.groupby("period"):
        if period not in out:
            continue
        ID = out[period]["ID"]
        for _, r in grp.iterrows():
            i, j = idx[r["from_ba"]], idx[r["to_ba"]]
            ID[i, j] = r["mwh"]  # EIA: positive = export from `from_ba` to `to_ba`
    return out


def consumption_hourly(
    fuel_long: pd.DataFrame,
    interchange: pd.DataFrame,
    demand_long: pd.DataFrame,
    bas: list[str],
) -> pd.DataFrame:
    """Per (ba, period): production and consumption CO2 (kg) and rates (kg/MWh)."""
    inputs = build_hourly_inputs(fuel_long, interchange, bas)
    dem = demand_long.copy()
    dem["mwh"] = pd.to_numeric(dem["mwh"], errors="coerce")
    dmap = {(r["ba"], r["period"]): r["mwh"] for _, r in dem.iterrows()}
    idx = {ba: i for i, ba in enumerate(bas)}

    rows = []
    for period, io in sorted(inputs.items()):
        rates = solve_consumption_rates(io["F"], io["P"], io["ID"])
        for ba, i in idx.items():
            d = dmap.get((ba, period), np.nan)
            cons_co2 = rates[i] * d if np.isfinite(d) else np.nan
            rows.append({
                "ba": ba, "period": period,
                "prod_co2_kg": float(io["F"][i]),
                "cons_rate_kg_per_mwh": float(rates[i]),
                "cons_co2_kg": float(cons_co2) if np.isfinite(cons_co2) else np.nan,
                "demand_mwh": float(d) if np.isfinite(d) else np.nan,
                "gen_mwh": float(io["P"][i]),
            })
    return pd.DataFrame(rows)


def consumption_factors(cons_hourly: pd.DataFrame) -> pd.DataFrame:
    """Per-BA consumption-based average factor (kg/MWh consumed) and prod AEF."""
    g = cons_hourly.groupby("ba", as_index=False).agg(
        cons_co2_kg=("cons_co2_kg", "sum"),
        demand_mwh=("demand_mwh", "sum"),
        prod_co2_kg=("prod_co2_kg", "sum"),
        gen_mwh=("gen_mwh", "sum"),
    )
    g["consumption_aef"] = g["cons_co2_kg"] / g["demand_mwh"].replace(0, np.nan)
    g["production_aef"] = g["prod_co2_kg"] / g["gen_mwh"].replace(0, np.nan)
    return g[["ba", "consumption_aef", "production_aef", "demand_mwh", "gen_mwh"]]


def consumption_mef(cons_hourly: pd.DataFrame, n_boot: int = 500) -> pd.DataFrame:
    """Consumption-based marginal factor: regress Δ(consumption CO2) on Δdemand.

    This is the siting-correct marginal number -- it charges a new load for the
    emissions embodied in the imports it will pull, not just local generation.
    """
    out = []
    for ba, grp in cons_hourly.groupby("ba"):
        s = grp.rename(columns={"cons_co2_kg": "co2_kg"})[["period", "co2_kg", "demand_mwh"]].copy()
        res = siler_evans_mef(s.assign(ba=ba), driver="demand", n_boot=n_boot)
        if res is None:
            continue
        # A constant load's marginal carbon is >= 0; raw estimates can dip
        # slightly negative in solar-saturated BAs under the 27-BA subnetwork
        # (dropped external imports). Keep the raw value, floor the usable one.
        out.append({
            "ba": ba,
            "consumption_mef_kg_per_mwh": max(0.0, res.mef_kg_per_mwh),
            "consumption_mef_raw": res.mef_kg_per_mwh,
            "ci_low": res.ci_low, "ci_high": res.ci_high,
            "r2": res.r2, "n_pairs": res.n_pairs,
        })
    return pd.DataFrame(out)
