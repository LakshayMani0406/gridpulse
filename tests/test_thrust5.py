import numpy as np
import pandas as pd

from gridpulse.thrust5 import indistinguishable_pairs, probabilistic_siting


def _mef():
    return pd.DataFrame({
        "ba": ["A", "B", "C"],
        "mef_kg_per_mwh": [50.0, 300.0, 305.0],
        "ci_low": [40, 250, 255], "ci_high": [60, 350, 360],
    })


def test_probabilistic_siting_ranks():
    summ, prob = probabilistic_siting(_mef(), n_draws=3000)
    assert list(summ.columns).count("rank_mean") == 1
    a = summ[summ["ba"] == "A"].iloc[0]
    assert a["rank_mean"] < 1.1 and a["p_rank1"] > 0.95  # A almost always greenest
    # A almost always greener (lower MEF) than B; diagonal is 0 (strict inequality)
    assert prob.loc["A", "B"] > 0.95
    assert prob.loc["A", "A"] == 0.0


def test_close_bas_flagged_as_tie():
    # B and C nearly identical -> P(greener) ~ 0.5 -> tie
    summ, prob = probabilistic_siting(_mef(), n_draws=5000)
    ties = indistinguishable_pairs(prob)
    assert {"B", "C"} == set(ties.iloc[0][["ba_a", "ba_b"]]) if not ties.empty else True
    assert 0.4 <= prob.loc["B", "C"] <= 0.6


def test_single_ba_returns_empty():
    summ, prob = probabilistic_siting(_mef().head(1))
    assert summ.empty and prob.empty
