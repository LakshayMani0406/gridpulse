"""Phase B orchestrator: consumption-based re-ranking + actual-vs-optimal gap.

Reads the live warehouse and produces the research findings:
  1. Consumption-based (import-adjusted) emissions via flow-tracing, and the
     consumption-based marginal factor -- the siting-correct number.
  2. How consumption-marginal re-ranks BAs vs production-marginal vs average.
  3. The MtCO2/yr gap between the actual data-center build-out (FracTracker) and
     a carbon-optimal one.

Flow-tracing runs on the modeled-BA subnetwork (imports/exports among the 27
analyzed BAs); this is a documented approximation of the full ~66-BA network.
Where EIA publishes consumption CO2, we validate the method against it.
"""
from __future__ import annotations

import json
import logging

import pandas as pd

from . import flowtrace, siting
from .config import Config, load_config
from .emissions import aef_by_ba, assemble_hourly, mef_by_ba
from .storage import Warehouse

log = logging.getLogger("gridpulse.phaseb")


def run_phaseb(cfg: Config | None = None, total_new_mw: float = 10000.0) -> dict:
    cfg = cfg or load_config()
    wh = Warehouse(cfg)
    fuel = wh.read("fuel_mix")
    demand = wh.read("demand")
    interchange = wh.read("interchange")
    if fuel.empty or interchange.empty:
        raise RuntimeError("warehouse missing fuel/interchange; run backfill first")

    fuel_long = fuel[["period", "ba", "fueltype", "mwh"]]
    demand_long = demand[["period", "ba", "mwh"]]
    bas = sorted(set(fuel_long["ba"]) & set(interchange["from_ba"]))

    # --- production-side factors (full window) ---
    asm = assemble_hourly(fuel_long, demand_long)
    aef = aef_by_ba(asm)
    prod_mef = mef_by_ba(asm, driver="demand", n_boot=500)

    # --- flow-traced consumption (interchange window) ---
    ix_periods = set(interchange["period"])
    fuel_ix = fuel_long[fuel_long["period"].isin(ix_periods)]
    dem_ix = demand_long[demand_long["period"].isin(ix_periods)]
    log.info("flow-tracing over %d hours x %d BAs", len(ix_periods), len(bas))
    cons_hourly = flowtrace.consumption_hourly(fuel_ix, interchange, dem_ix, bas)
    cons_fac = flowtrace.consumption_factors(cons_hourly)
    cons_mef = flowtrace.consumption_mef(cons_hourly, n_boot=500)

    ranking = siting.combined_ranking(aef, prod_mef, cons_mef)

    # deliverability caps: a BA can realistically absorb new DC load up to a
    # fraction of its own mean demand. Used for the constrained optimal.
    mean_dem = (demand_long.assign(mwh=pd.to_numeric(demand_long["mwh"], errors="coerce"))
                .groupby("ba")["mwh"].mean())
    capacity_mw = {ba: 0.20 * float(mean_dem.get(ba, 0.0)) for ba in ranking["ba"]}

    # --- actual vs optimal siting gap (FracTracker) ---
    # Headline uses the *production* MEF (robust, positive, validated). The
    # consumption MEF is reported as the frontier basis but is noisier on the
    # 27-BA subnetwork, so it's secondary.
    gap = {}
    facilities = None
    try:
        facilities = siting.load_fractracker(cfg, statuses=siting.BUILT_STATUSES, require_mw=True)
        alloc = siting.allocate_facilities(facilities, restrict=set(ranking["ba"]))
        gap = siting.actual_vs_optimal(ranking, alloc, total_new_mw=total_new_mw,
                                       factor_col="prod_mef", capacity_mw=capacity_mw)
        gap_cons = siting.actual_vs_optimal(ranking, alloc, total_new_mw=total_new_mw,
                                            factor_col="cons_mef", capacity_mw=capacity_mw)
        gap["gap_constrained_mt_co2_yr_cons_basis"] = gap_cons.get("gap_constrained_mt_co2_yr")
        gap["best_ba_cons_basis"] = gap_cons.get("best_ba")
    except Exception as e:  # noqa: BLE001
        log.warning("siting-gap step skipped: %s", e)
        alloc = pd.DataFrame()

    out = {
        "n_bas": len(ranking),
        "interchange_hours": len(ix_periods),
        "ranking": ranking,
        "consumption_factors": cons_fac,
        "gap": gap,
        "allocation": alloc,
    }
    _write_findings(cfg, out)
    return out


def _write_findings(cfg: Config, out: dict) -> None:
    r = out["ranking"]
    gap = out["gap"]
    lines = ["# gridpulse FINDINGS (real EIA data)", ""]
    lines += [
        "## 1. Average vs. marginal vs. consumption-based re-ranks siting",
        "",
        "Three bases per balancing authority: **AEF** (average), **production MEF** "
        "(Siler-Evans on own generation), and **consumption MEF** (import-adjusted, "
        "via interchange flow-tracing -- the frontier siting number).",
        "",
        f"Flow-tracing ran over {out['interchange_hours']} hours across {out['n_bas']} "
        "modeled BAs (subnetwork of the ~66-BA US grid). Consumption MEF is floored at "
        "0 (a constant load's marginal carbon is non-negative; raw estimates dip "
        "negative in solar-saturated BAs under the subnetwork approximation).",
        "",
        "| BA | AEF | prod MEF | cons MEF | rank(AEF) | rank(prodMEF) | rank(consMEF) | AEF→consMEF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, x in r.iterrows():
        lines.append(
            f"| {x['ba']} | {x['aef']:.0f} | {x['prod_mef']:.0f} | {x['cons_mef']:.0f} "
            f"| {int(x['rank_aef'])} | {int(x['rank_prod_mef'])} | {int(x['rank_cons_mef'])} "
            f"| {int(x['rerank_aef_to_cons']):+d} |"
        )
    movers = r.reindex(r["rerank_aef_to_cons"].abs().sort_values(ascending=False).index).head(4)
    ap = r.reindex((r["rank_aef"] - r["rank_prod_mef"]).abs().sort_values(ascending=False).index).head(3)
    lines += [
        "",
        "Average vs. production-marginal already re-ranks sharply: " +
        ", ".join(f"**{m['ba']}** ({int(m['rank_aef'] - m['rank_prod_mef']):+d})" for _, m in ap.iterrows())
        + " (rank moves, average→marginal). Adding import-adjustment (consumption MEF) "
        "moves them further: " +
        ", ".join(f"**{m['ba']}** ({int(m['rerank_aef_to_cons']):+d})" for _, m in movers.iterrows())
        + ".", "",
        "Positive rerank = a BA that looks dirtier on average is cleaner on the margin "
        "(its extra MWh displaces coal with gas/renewables); negative = looks clean on "
        "average but its marginal/imported MWh is dirty.", "",
    ]

    if gap:
        lines += [
            "## 2. Actual vs. carbon-optimal data-center build-out",
            "",
            f"FracTracker's tracked build-out (Operating + approved/under-construction, "
            f"with capacity) is allocated to modeled BAs by observed share; we then site "
            f"{gap['total_new_mw']:.0f} MW of new load and price it on the **production "
            "marginal** factor (robust, validated). Capacity-constrained optimal = greedy "
            "cleanest-first, each BA capped at 20% of its own mean demand (deliverability).",
            "",
            f"- **Actual** allocation: **{gap['actual_mt_co2_yr']:.2f} MtCO2/yr**",
            f"- **Carbon-optimal, capacity-constrained**: "
            f"**{gap.get('optimal_constrained_mt_co2_yr', float('nan')):.2f} MtCO2/yr** "
            f"→ **gap {gap.get('gap_constrained_mt_co2_yr', float('nan')):.1f} MtCO2/yr "
            f"({gap.get('gap_constrained_pct', float('nan')):.0f}% of actual)**",
            f"- Carbon-optimal, unconstrained (all load in cleanest BA, **{gap['best_ba']}** "
            f"@ {gap['best_factor']:.0f} kg/MWh): {gap['optimal_mt_co2_yr']:.2f} MtCO2/yr "
            f"→ gap {gap['gap_mt_co2_yr']:.1f} MtCO2/yr (theoretical floor; ignores deliverability)",
            f"- Consumption-marginal basis (frontier): constrained gap "
            f"{gap.get('gap_constrained_mt_co2_yr_cons_basis', float('nan')):.1f} MtCO2/yr",
            "",
            "Headline: even respecting a 20%-of-local-demand cap per BA, aligning the "
            f"build-out to marginal carbon avoids ~**{gap.get('gap_constrained_mt_co2_yr', float('nan')):.0f} "
            "MtCO2/yr** on the production-marginal basis.",
            "",
            "_Data: FracTracker Alliance National Data Centers Tracker (non-commercial "
            "use, credited). Flow-tracing: de Chalendar et al. 2019. Subnetwork of 27 "
            "modeled BAs; facility→BA by nearest load center._",
            "",
        ]
    cfg.repo_root.joinpath("FINDINGS.md").write_text("\n".join(lines) + "\n")
    # also drop machine-readable outputs
    r.to_csv(cfg.figs_dir.parent / "ranking.csv", index=False)
    (cfg.figs_dir.parent / "gap.json").write_text(json.dumps(gap, indent=2, default=str))
    log.info("wrote FINDINGS.md + ranking.csv + gap.json")
