"""Thrust 6 (capstone): specification-curve / multiverse over accounting choices.

The carbon-optimal siting recommendation depends on four contested analyst
choices, each of which can invert the "greenest BA" ranking:

    temporal    : short-run dispatch margin  vs  long-run induced capacity (LRMER)
    accounting  : production-based            vs  consumption-based (import-adjusted)
    resolution  : balancing-authority        vs  nodal (congestion)
    method      : regression (Siler-Evans)   vs  dispatch/instrument  vs  Cambium

We compute a carbon factor per BA under every available specification, rank BAs
under each, and report the *distribution* of ranks. Regions with low rank
variance are robustly good/bad; high-variance regions flip with the method — the
honest headline. Method ref: Simonsohn, Simmons & Nelson (2020), "Specification
curve analysis," Nature Human Behaviour 4:1208, doi:10.1038/s41562-020-0912-z.
"""
from __future__ import annotations

import pandas as pd

from . import emissions, flowtrace
from .causal_mef import triangulate_mef
from .config import HAS_MATPLOTLIB

# Each spec: name -> dict(temporal, accounting, resolution, method).
SPEC_TAGS = {
    "AEF (avg, prod, BA)": dict(temporal="average", accounting="production", resolution="BA", method="ratio"),
    "MEF short-run prod (regression)": dict(temporal="short-run", accounting="production", resolution="BA", method="regression"),
    "MEF short-run prod (VRE instrument)": dict(temporal="short-run", accounting="production", resolution="BA", method="dispatch"),
    "MEF short-run consumption (flow-trace)": dict(temporal="short-run", accounting="consumption", resolution="BA", method="flow-tracing"),
    "LRMER long-run (Cambium)": dict(temporal="long-run", accounting="production", resolution="BA", method="Cambium"),
    "LME nodal (ERCOT)": dict(temporal="short-run", accounting="production", resolution="nodal", method="dispatch"),
}


def assemble_specifications(
    fuel_long: pd.DataFrame,
    demand_long: pd.DataFrame,
    interchange: pd.DataFrame | None = None,
    lrmer: pd.Series | None = None,
    nodal_lme: pd.Series | None = None,
) -> dict[str, pd.Series]:
    """Compute a per-BA carbon factor (kg/MWh) under each available specification.

    Returns {spec_name: Series indexed by BA}. Specs requiring data not present
    (interchange, LRMER, nodal) are simply omitted.
    """
    specs: dict[str, pd.Series] = {}
    asm = emissions.assemble_hourly(fuel_long, demand_long)

    aef = emissions.aef_by_ba(asm).set_index("ba")["aef_kg_per_mwh"]
    specs["AEF (avg, prod, BA)"] = aef

    mef = emissions.mef_by_ba(asm, driver="demand", n_boot=200).set_index("ba")["mef_kg_per_mwh"]
    specs["MEF short-run prod (regression)"] = mef

    tri = triangulate_mef(fuel_long, demand_long, sorted(asm["ba"].unique()))
    if not tri.empty and tri["mef_vre_ramp"].notna().any():
        specs["MEF short-run prod (VRE instrument)"] = tri.set_index("ba")["mef_vre_ramp"].dropna()

    if interchange is not None and not interchange.empty:
        bas = sorted(set(fuel_long["ba"]) & set(interchange["from_ba"]))
        ixp = set(interchange["period"])
        ch = flowtrace.consumption_hourly(
            fuel_long[fuel_long["period"].isin(ixp)], interchange,
            demand_long[demand_long["period"].isin(ixp)], bas)
        cm = flowtrace.consumption_mef(ch, n_boot=200)
        if not cm.empty:
            specs["MEF short-run consumption (flow-trace)"] = cm.set_index("ba")["consumption_mef_kg_per_mwh"]

    if lrmer is not None and not lrmer.empty:
        specs["LRMER long-run (Cambium)"] = lrmer
    if nodal_lme is not None and not nodal_lme.empty:
        specs["LME nodal (ERCOT)"] = nodal_lme
    return specs


def spec_curve(specs: dict[str, pd.Series]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rank BAs (1 = greenest) under every spec; return (ranks, robustness).

    ranks: index=BA, columns=spec, values=rank (lower factor -> better rank).
    robustness: per-BA rank mean/min/max/std + a robustness verdict.
    """
    factors = pd.DataFrame(specs)  # BA x spec of carbon factors
    # Only BAs present in every spec get a comparable full-ranking; keep all but
    # rank within each spec over its available BAs, then align.
    ranks = factors.rank(axis=0, method="min")  # per-column ranks (1 = lowest factor)
    rob = pd.DataFrame({
        "n_specs": ranks.notna().sum(axis=1),
        "rank_mean": ranks.mean(axis=1),
        "rank_min": ranks.min(axis=1),
        "rank_max": ranks.max(axis=1),
        "rank_std": ranks.std(axis=1),
    })
    n_ba = len(factors)
    rob["rank_range"] = rob["rank_max"] - rob["rank_min"]
    # Robust-good: always in the cleaner third. Robust-bad: always dirtier third.
    third = max(1, n_ba // 3)
    rob["verdict"] = "flips"
    rob.loc[rob["rank_max"] <= third, "verdict"] = "robust-green"
    rob.loc[rob["rank_min"] >= n_ba - third + 1, "verdict"] = "robust-dirty"
    rob = rob.sort_values("rank_mean")
    return ranks, rob


def top_choice_stability(specs: dict[str, pd.Series], k: int = 3) -> pd.DataFrame:
    """How often each BA lands in the greenest top-k across specifications."""
    factors = pd.DataFrame(specs)
    hits = {}
    for col in factors.columns:
        s = factors[col].dropna()
        for ba in s.nsmallest(k).index:
            hits[ba] = hits.get(ba, 0) + 1
    n = factors.shape[1]
    out = pd.DataFrame([{"ba": ba, "top{}_count".format(k): c, "share_of_specs": c / n}
                        for ba, c in hits.items()])
    return out.sort_values(f"top{k}_count", ascending=False).reset_index(drop=True)


def chart_spec_curve(ranks: pd.DataFrame, rob: pd.DataFrame, out, focus_n: int = 16):
    """Multiverse figure: each BA's rank across specs, ordered by mean rank."""
    if not HAS_MATPLOTLIB:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = rob.head(focus_n).index.tolist()
    colors = {"robust-green": "#2E7D32", "robust-dirty": "#C62828", "flips": "#F9A825"}
    fig, ax = plt.subplots(figsize=(12, 7))
    for i, ba in enumerate(order):
        rvals = ranks.loc[ba].dropna()
        ax.scatter(rvals.values, [i] * len(rvals), s=40,
                   color=colors[rob.loc[ba, "verdict"]], alpha=0.8, zorder=3)
        ax.plot([rvals.min(), rvals.max()], [i, i], color=colors[rob.loc[ba, "verdict"]],
                alpha=0.4, lw=2, zorder=2)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    ax.set_xlabel("Siting rank across specifications (1 = greenest)")
    ax.set_title("Multiverse of carbon-optimal siting\n"
                 "green = robustly clean · red = robustly dirty · yellow = verdict flips with method")
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=9, label=v)
               for v, c in colors.items()]
    ax.legend(handles=handles, loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out
