"""Carbon-aware siting: rank BAs by the marginal carbon of a new data center.

A new data center is an increment of load, so its annual carbon is
``load_MW * 8760 h * MEF``. Ranking BAs by MEF (marginal) versus AEF (average)
can *invert* the "greenest" ordering -- the headline gridpulse result.
"""
from __future__ import annotations

import pandas as pd

HOURS_PER_YEAR = 8760.0


def annual_marginal_co2(load_mw: float, mef_kg_per_mwh: float) -> float:
    """Tonnes CO2/yr from adding a constant ``load_mw`` at marginal factor MEF."""
    return load_mw * HOURS_PER_YEAR * mef_kg_per_mwh / 1000.0


def siting_index(
    mef_df: pd.DataFrame,
    aef_df: pd.DataFrame,
    load_mw: float = 100.0,
) -> pd.DataFrame:
    """Join MEF and AEF, rank BAs both ways, flag rank inversions.

    Returns one row per BA with marginal and average rankings and the annual
    carbon of siting a ``load_mw`` facility there under each factor.
    """
    m = mef_df[["ba", "mef_kg_per_mwh", "ci_low", "ci_high"]].copy()
    a = aef_df[["ba", "aef_kg_per_mwh"]].copy()
    df = m.merge(a, on="ba", how="inner")

    df["annual_co2_t_marginal"] = annual_marginal_co2(load_mw, df["mef_kg_per_mwh"])
    df["annual_co2_t_average"] = annual_marginal_co2(load_mw, df["aef_kg_per_mwh"])

    df["rank_marginal"] = df["mef_kg_per_mwh"].rank(method="min").astype(int)
    df["rank_average"] = df["aef_kg_per_mwh"].rank(method="min").astype(int)
    df["rank_shift"] = df["rank_average"] - df["rank_marginal"]

    # A BA "looks clean on average but is dirty on the margin" when its average
    # rank is much better (smaller) than its marginal rank.
    df["avg_marginal_gap_kg"] = df["mef_kg_per_mwh"] - df["aef_kg_per_mwh"]
    return df.sort_values("mef_kg_per_mwh").reset_index(drop=True)


def rank_inversions(siting: pd.DataFrame, top_k: int = 5) -> pd.DataFrame:
    """BAs where average- and marginal-optimal siting disagree the most.

    Concretely: regions in the cleanest ``top_k`` on average but not on the
    margin (or vice-versa) -- the cases a naive average-based analysis gets wrong.
    """
    clean_avg = set(siting.nsmallest(top_k, "aef_kg_per_mwh")["ba"])
    clean_marg = set(siting.nsmallest(top_k, "mef_kg_per_mwh")["ba"])
    disagree = clean_avg.symmetric_difference(clean_marg)
    out = siting[siting["ba"].isin(disagree)].copy()
    out["clean_on_average"] = out["ba"].isin(clean_avg)
    out["clean_on_margin"] = out["ba"].isin(clean_marg)
    return out.sort_values("rank_shift", ascending=False).reset_index(drop=True)


def siting_gap(
    siting: pd.DataFrame,
    allocation: dict[str, float],
    load_mw_total: float,
) -> dict:
    """Carbon gap between an actual/allocated build-out and the marginal-optimal one.

    ``allocation`` maps BA -> share (fractions summing to ~1) of ``load_mw_total``.
    The optimal build-out puts all load in the lowest-MEF BA(s). Returns the
    actual, optimal, and gap annual CO2 in tonnes/yr.
    """
    s = siting.set_index("ba")
    actual_t = 0.0
    for ba, share in allocation.items():
        if ba in s.index:
            actual_t += annual_marginal_co2(load_mw_total * share, s.loc[ba, "mef_kg_per_mwh"])
    # Optimal: all load in the single lowest-MEF region.
    best_ba = s["mef_kg_per_mwh"].idxmin()
    optimal_t = annual_marginal_co2(load_mw_total, s.loc[best_ba, "mef_kg_per_mwh"])
    return {
        "actual_mt_co2_yr": actual_t / 1e6,
        "optimal_mt_co2_yr": optimal_t / 1e6,
        "gap_mt_co2_yr": (actual_t - optimal_t) / 1e6,
        "best_ba": str(best_ba),
        "best_mef": float(s.loc[best_ba, "mef_kg_per_mwh"]),
    }
