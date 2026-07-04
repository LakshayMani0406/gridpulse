"""Thrust 5: probabilistic, uncertainty-aware siting.

A point ranking hides that many BAs' marginal factors overlap within their
confidence intervals -- so the "greenest" verdict is often not statistically
distinguishable. We propagate the MEF bootstrap uncertainty into the siting
ranking: Monte-Carlo draw each BA's MEF from its CI, rank every draw, and report
each BA's *rank distribution*, P(in greenest top-k), and the pairwise matrix
P(A greener than B).

This is the uncertainty layer of forward-looking siting; combined with Cambium's
forward LRMER scenarios (Thrust 1) it gives a forward-margin ranking with bands.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _sigma_from_ci(mef: float, lo: float, hi: float) -> float:
    """Std implied by a ~95% CI [lo, hi]; fall back to 10% of the point."""
    if np.isfinite(lo) and np.isfinite(hi) and hi > lo:
        return (hi - lo) / (2 * 1.959963985)
    return abs(mef) * 0.10 + 1e-9


def probabilistic_siting(mef_df: pd.DataFrame, n_draws: int = 5000, top_k: int = 5,
                         seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rank distributions + pairwise P(greener) from MEF bootstrap CIs.

    ``mef_df`` needs columns ba, mef_kg_per_mwh, ci_low, ci_high.
    Returns (rank_summary, prob_greener_matrix).
    """
    d = mef_df.dropna(subset=["mef_kg_per_mwh"]).reset_index(drop=True)
    bas = d["ba"].tolist()
    n = len(bas)
    if n < 2:
        return pd.DataFrame(), pd.DataFrame()
    mu = d["mef_kg_per_mwh"].to_numpy(float)
    sig = np.array([_sigma_from_ci(m, lo, hi) for m, lo, hi in
                    zip(mu, d.get("ci_low", pd.Series([np.nan] * n)),
                        d.get("ci_high", pd.Series([np.nan] * n)))])
    rng = np.random.default_rng(seed)
    draws = rng.normal(mu, sig, size=(n_draws, n))       # n_draws x n_ba MEF samples
    order = draws.argsort(axis=1)                         # per draw, ascending (greenest first)
    ranks = np.empty_like(order)
    rows = np.arange(n_draws)[:, None]
    ranks[rows, order] = np.arange(1, n + 1)             # rank per BA per draw

    summary = pd.DataFrame({
        "ba": bas,
        "mef": mu,
        "rank_mean": ranks.mean(axis=0),
        "rank_p05": np.percentile(ranks, 5, axis=0),
        "rank_p95": np.percentile(ranks, 95, axis=0),
        "p_top{}".format(top_k): (ranks <= top_k).mean(axis=0),
        "p_rank1": (ranks == 1).mean(axis=0),
    }).sort_values("rank_mean").reset_index(drop=True)

    # pairwise P(row greener/lower-MEF than col)
    prob = np.zeros((n, n))
    for i in range(n):
        prob[i] = (draws[:, i][:, None] < draws).mean(axis=0)
    prob_df = pd.DataFrame(prob, index=bas, columns=bas)
    return summary, prob_df


def indistinguishable_pairs(prob_df: pd.DataFrame, low: float = 0.4, high: float = 0.6) -> pd.DataFrame:
    """Pairs whose greener-than probability is near 50% (statistical tie)."""
    rows = []
    bas = list(prob_df.index)
    for i, a in enumerate(bas):
        for b in bas[i + 1:]:
            p = prob_df.loc[a, b]
            if low <= p <= high:
                rows.append({"ba_a": a, "ba_b": b, "p_a_greener": float(p)})
    return pd.DataFrame(rows).sort_values("p_a_greener").reset_index(drop=True) \
        if rows else pd.DataFrame(columns=["ba_a", "ba_b", "p_a_greener"])
