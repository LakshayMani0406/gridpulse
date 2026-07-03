"""Ground siting in real data-center locations and quantify the carbon gap.

Maps facilities (lat/lon or state + MW) to balancing authorities, builds the
actual build-out allocation, and compares three ranking bases -- average (AEF),
production-marginal (MEF), and consumption-marginal (import-adjusted MEF) --
then computes the MtCO2/yr gap between where load is actually going and where a
consumption-marginal-optimal build-out would put it.
"""
from __future__ import annotations

import logging
import urllib.request

import numpy as np
import pandas as pd

from .analysis import HOURS_PER_YEAR
from .config import Config
from .regions import REGIONS, REGION_CODES

log = logging.getLogger("gridpulse.siting")

# FracTracker National Data Centers Tracker (Google Sheet CSV export).
# 1,593 facilities, lat/long on 100% of rows, MW on ~514. Non-commercial use
# with credit to FracTracker Alliance. https://www.fractracker.org/2025/07/national-data-centers-tracker/
FRACTRACKER_CSV = (
    "https://docs.google.com/spreadsheets/d/"
    "1JJ6kcVo-NjlAYtznwHOki2DVl4WWV6lhy-eXhFCdKKU/export?format=csv"
)
# "Actual build-out" statuses: real capacity on the grid or committed to it.
# (Strings match FracTracker's exact `status` values.)
BUILT_STATUSES = {"Operating", "Expanding", "Approved/Permitted/Under construction"}


def load_fractracker(cfg: Config, statuses: set[str] | None = None,
                     require_mw: bool = True) -> pd.DataFrame:
    """Download (cached) and clean FracTracker facilities -> [mw, lat, lon, state, status].

    ``statuses`` filters by build status (default: all). ``require_mw`` drops
    rows without a numeric MW capacity.
    """
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.raw_dir / "fractracker_datacenters.csv"
    if not path.exists():
        req = urllib.request.Request(FRACTRACKER_CSV, headers={"User-Agent": "gridpulse/0.1"})
        with urllib.request.urlopen(req, timeout=cfg.request_timeout) as r:
            path.write_bytes(r.read())
        log.info("downloaded FracTracker tracker -> %s", path.name)
    df = pd.read_csv(path)
    df = df.rename(columns={"long": "lon"})
    df["mw"] = pd.to_numeric(df.get("mw"), errors="coerce")
    for c in ("lat", "lon"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    if statuses:
        df = df[df.get("status").isin(statuses)]
    if require_mw:
        df = df[df["mw"].notna() & (df["mw"] > 0)]
    df = df.dropna(subset=["lat", "lon"])
    keep = [c for c in ["mw", "lat", "lon", "state", "status", "operator_name"] if c in df.columns]
    return df[keep].reset_index(drop=True)

# Approximate: which BA serves each state (primary). Coarse but lets us place
# facilities that only have a state, not coordinates.
STATE_TO_BA = {
    "CA": "CISO", "TX": "ERCO", "PA": "PJM", "OH": "PJM", "VA": "PJM", "NJ": "PJM",
    "MD": "PJM", "IL": "MISO", "MI": "MISO", "IN": "MISO", "MN": "MISO", "MO": "AECI",
    "IA": "MISO", "KS": "SWPP", "OK": "SWPP", "NE": "SWPP", "MA": "ISNE", "CT": "ISNE",
    "ME": "ISNE", "NH": "ISNE", "RI": "ISNE", "VT": "ISNE", "NY": "NYIS", "OR": "PGE",
    "WA": "BPAT", "UT": "PACE", "CO": "PSCO", "NM": "PNM", "AZ": "AZPS", "NV": "NEVP",
    "ID": "IPCO", "GA": "SOCO", "AL": "SOCO", "MS": "SOCO", "TN": "TVA", "NC": "DUK",
    "SC": "DUK", "FL": "FPL", "KY": "LGEE", "WY": "PACE", "MT": "WACM",
}


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def facility_to_ba(row: pd.Series, restrict: set[str] | None = None) -> str | None:
    """Assign a facility to a BA: nearest load-center by lat/lon, else state map."""
    codes = restrict or set(REGION_CODES)
    lat, lon = row.get("lat"), row.get("lon")
    if pd.notna(lat) and pd.notna(lon):
        best, bestd = None, np.inf
        for code in codes:
            reg = REGIONS[code]
            d = _haversine(float(lat), float(lon), reg.lat, reg.lon)
            if d < bestd:
                best, bestd = code, d
        return best
    st = row.get("state")
    if pd.notna(st):
        ba = STATE_TO_BA.get(str(st).upper())
        return ba if (ba in codes) else None
    return None


def allocate_facilities(facilities: pd.DataFrame, restrict: set[str] | None = None) -> pd.DataFrame:
    """Aggregate facility MW to per-BA totals and shares.

    ``facilities`` needs a ``mw`` column and either ``lat``/``lon`` or ``state``.
    Returns per-BA total_mw, n_facilities, and share of total.
    """
    df = facilities.copy()
    df["ba"] = df.apply(lambda r: facility_to_ba(r, restrict), axis=1)
    df = df.dropna(subset=["ba"])
    g = df.groupby("ba", as_index=False).agg(total_mw=("mw", "sum"), n_facilities=("mw", "size"))
    total = g["total_mw"].sum()
    g["share"] = g["total_mw"] / total if total else 0.0
    return g.sort_values("total_mw", ascending=False).reset_index(drop=True)


def combined_ranking(
    aef_df: pd.DataFrame,
    prod_mef_df: pd.DataFrame,
    cons_mef_df: pd.DataFrame,
) -> pd.DataFrame:
    """One table with AEF, production MEF, consumption MEF and all three ranks."""
    a = aef_df[["ba", "aef_kg_per_mwh"]].rename(columns={"aef_kg_per_mwh": "aef"})
    p = prod_mef_df[["ba", "mef_kg_per_mwh"]].rename(columns={"mef_kg_per_mwh": "prod_mef"})
    c = cons_mef_df[["ba", "consumption_mef_kg_per_mwh"]].rename(
        columns={"consumption_mef_kg_per_mwh": "cons_mef"})
    df = a.merge(p, on="ba", how="inner").merge(c, on="ba", how="inner")
    for col, rk in [("aef", "rank_aef"), ("prod_mef", "rank_prod_mef"), ("cons_mef", "rank_cons_mef")]:
        df[rk] = df[col].rank(method="min").astype(int)
    # Re-ranking effect of moving from average to the correct consumption-marginal.
    df["rerank_aef_to_cons"] = df["rank_aef"] - df["rank_cons_mef"]
    df["rerank_prod_to_cons"] = df["rank_prod_mef"] - df["rank_cons_mef"]
    return df.sort_values("cons_mef").reset_index(drop=True)


def actual_vs_optimal(
    ranking: pd.DataFrame,
    allocation: pd.DataFrame,
    total_new_mw: float,
    factor_col: str = "cons_mef",
    capacity_mw: dict[str, float] | None = None,
) -> dict:
    """MtCO2/yr for the actual build-out vs. a carbon-optimal one (same total MW).

    Actual = allocate ``total_new_mw`` by observed facility shares. Two optima:
    unconstrained (all load in the single lowest-``factor_col`` BA -- a floor),
    and, if ``capacity_mw`` is given, a deliverability-constrained greedy fill
    (cleanest BAs first, capped per BA). Emissions use the marginal factor.
    """
    r = ranking.set_index("ba")
    alloc = allocation.set_index("ba")
    actual_kg = 0.0
    covered_mw = 0.0
    for ba, row in alloc.iterrows():
        if ba in r.index:
            mw = total_new_mw * row["share"]
            actual_kg += mw * HOURS_PER_YEAR * r.loc[ba, factor_col]
            covered_mw += mw
    best_ba = r[factor_col].idxmin()
    optimal_kg = total_new_mw * HOURS_PER_YEAR * r.loc[best_ba, factor_col]

    out = {
        "factor": factor_col,
        "total_new_mw": total_new_mw,
        "actual_mt_co2_yr": actual_kg / 1e9,
        "optimal_unconstrained_mt_co2_yr": optimal_kg / 1e9,
        "gap_unconstrained_mt_co2_yr": (actual_kg - optimal_kg) / 1e9,
        "best_ba": str(best_ba),
        "best_factor": float(r.loc[best_ba, factor_col]),
        "covered_share": covered_mw / total_new_mw if total_new_mw else 0.0,
    }

    # Capacity-constrained optimal: greedily fill cleanest BAs first, but cap the
    # new load each BA can absorb (deliverability). Far more defensible than
    # dumping all load on the single greenest BA.
    if capacity_mw is not None:
        remaining = total_new_mw
        opt_c_kg = 0.0
        placed = {}
        for ba in r.sort_values(factor_col).index:
            if remaining <= 0:
                break
            cap = float(capacity_mw.get(ba, 0.0))
            take = min(cap, remaining)
            if take > 0:
                opt_c_kg += take * HOURS_PER_YEAR * r.loc[ba, factor_col]
                placed[ba] = take
                remaining -= take
        # any load that can't be placed under caps stays at the actual (dirtiest) rate
        if remaining > 0:
            opt_c_kg += remaining * HOURS_PER_YEAR * r[factor_col].max()
        out["optimal_constrained_mt_co2_yr"] = opt_c_kg / 1e9
        out["gap_constrained_mt_co2_yr"] = (actual_kg - opt_c_kg) / 1e9
        out["gap_constrained_pct"] = (100 * (actual_kg - opt_c_kg) / actual_kg) if actual_kg else float("nan")
        out["constrained_placement_mw"] = {k: round(v) for k, v in placed.items()}
    # keep legacy keys for the unconstrained gap
    out["optimal_mt_co2_yr"] = out["optimal_unconstrained_mt_co2_yr"]
    out["gap_mt_co2_yr"] = out["gap_unconstrained_mt_co2_yr"]
    out["gap_pct"] = 100 * (actual_kg - optimal_kg) / actual_kg if actual_kg else float("nan")
    return out
