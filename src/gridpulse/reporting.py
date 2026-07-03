"""Charts and a markdown report. Synthetic-data figures are watermarked.

Matplotlib is optional (``.[prod]``); if absent, chart functions no-op and the
text report is still produced.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .config import HAS_MATPLOTLIB

log = logging.getLogger("gridpulse.reporting")

# Colorblind-safe pair: average vs marginal.
C_AVG = "#4C78A8"   # blue
C_MARG = "#E45756"  # red


def _watermark(ax, synthetic: bool) -> None:
    if synthetic:
        ax.figure.text(
            0.5, 0.5, "SYNTHETIC", fontsize=60, color="gray", alpha=0.18,
            ha="center", va="center", rotation=30, zorder=100,
        )


def chart_aef_vs_mef(siting: pd.DataFrame, out: Path, synthetic: bool = False) -> Path | None:
    if not HAS_MATPLOTLIB:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = siting.sort_values("mef_kg_per_mwh")
    fig, ax = plt.subplots(figsize=(11, 7))
    y = range(len(d))
    ax.barh([i + 0.2 for i in y], d["aef_kg_per_mwh"], height=0.4, color=C_AVG, label="Average (AEF)")
    ax.barh([i - 0.2 for i in y], d["mef_kg_per_mwh"], height=0.4, color=C_MARG, label="Marginal (MEF)")
    ax.set_yticks(list(y))
    ax.set_yticklabels(d["ba"])
    ax.set_xlabel("CO2 emission factor (kg / MWh)")
    ax.set_title("Average vs. marginal emission factor by balancing authority")
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    _watermark(ax, synthetic)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def chart_rank_scatter(siting: pd.DataFrame, out: Path, synthetic: bool = False) -> Path | None:
    if not HAS_MATPLOTLIB:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(siting["aef_kg_per_mwh"], siting["mef_kg_per_mwh"], c=C_MARG, s=60, zorder=3)
    for _, r in siting.iterrows():
        ax.annotate(r["ba"], (r["aef_kg_per_mwh"], r["mef_kg_per_mwh"]),
                    fontsize=7, xytext=(3, 3), textcoords="offset points")
    lim = max(siting["aef_kg_per_mwh"].max(), siting["mef_kg_per_mwh"].max()) * 1.05
    ax.plot([0, lim], [0, lim], "--", color="gray", alpha=0.6, label="AEF = MEF")
    ax.set_xlabel("Average emission factor (kg/MWh)")
    ax.set_ylabel("Marginal emission factor (kg/MWh)")
    ax.set_title("Where marginal diverges from average\n(above line: dirtier on the margin)")
    ax.legend()
    ax.grid(alpha=0.3)
    _watermark(ax, synthetic)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def chart_validation(agree: pd.DataFrame, out: Path) -> Path | None:
    """Scatter of computed AEF vs EIA-published AEF per BA (Phase A ground truth)."""
    if not HAS_MATPLOTLIB or agree.empty:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(agree["eia_aef"], agree["computed_aef"], c=C_MARG, s=60, zorder=3)
    for _, r in agree.iterrows():
        ax.annotate(r["ba"], (r["eia_aef"], r["computed_aef"]),
                    fontsize=7, xytext=(3, 3), textcoords="offset points")
    lim = max(agree["eia_aef"].max(), agree["computed_aef"].max()) * 1.05
    ax.plot([0, lim], [0, lim], "--", color="gray", alpha=0.6, label="perfect agreement")
    ax.set_xlabel("EIA-published AEF (kg/MWh)")
    ax.set_ylabel("gridpulse computed AEF (kg/MWh)")
    ax.set_title("Validation: computed AEF vs. EIA's published hourly CO2")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def build_report(
    siting: pd.DataFrame,
    inversions: pd.DataFrame,
    out: Path,
    synthetic: bool = False,
    extra_sections: list[str] | None = None,
) -> Path:
    lines = ["# gridpulse report", ""]
    if synthetic:
        lines += ["> **SYNTHETIC DATA** — validation fixture, not real EIA data.", ""]
    lines += [
        f"Balancing authorities analyzed: **{len(siting)}**", "",
        "## Siting ranking (by marginal emission factor)", "",
        "| Rank | BA | MEF (kg/MWh) | AEF (kg/MWh) | rank shift (avg→marg) |",
        "|---:|---|---:|---:|---:|",
    ]
    for _, r in siting.head(15).iterrows():
        lines.append(
            f"| {int(r['rank_marginal'])} | {r['ba']} | {r['mef_kg_per_mwh']:.0f} "
            f"| {r['aef_kg_per_mwh']:.0f} | {int(r['rank_shift']):+d} |"
        )
    lines += ["", "## Rank inversions (average-based analysis gets these wrong)", ""]
    if inversions.empty:
        lines.append("_No inversions in the top set._")
    else:
        lines += ["| BA | clean on average | clean on margin | MEF−AEF (kg/MWh) |",
                  "|---|:---:|:---:|---:|"]
        for _, r in inversions.iterrows():
            lines.append(
                f"| {r['ba']} | {'✓' if r['clean_on_average'] else ''} "
                f"| {'✓' if r['clean_on_margin'] else ''} | {r['avg_marginal_gap_kg']:+.0f} |"
            )
    if extra_sections:
        lines += ["", *extra_sections]
    out.write_text("\n".join(lines) + "\n")
    return out
