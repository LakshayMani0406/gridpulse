import numpy as np
import pandas as pd

from gridpulse import nodal


def _profile():
    rng = np.random.default_rng(0)
    nodes = [f"N{i}" for i in range(200)]
    mcc = np.concatenate([rng.normal(30, 5, 50), rng.normal(0, 2, 100), rng.normal(-25, 5, 50)])
    return pd.DataFrame({"NODE": nodes, "mcc_mean": mcc, "mcc_std": 5.0,
                         "mcc_p10": mcc - 5, "mcc_p90": mcc + 5, "n": 48})


def test_nodal_lme_index_direction_and_bounds():
    p = _profile()
    lme = nodal.nodal_lme_index(p, system_mef=140.0, sensitivity=0.5)
    # import-constrained (high MCC) -> above system; export-constrained -> below
    top = lme.iloc[0]
    bot = lme.iloc[-1]
    assert top["nodal_lme_rel"] > 140.0 > bot["nodal_lme_rel"]
    # bounded by +/- sensitivity
    assert lme["nodal_lme_rel"].max() <= 140.0 * 1.5 + 1e-6
    assert lme["nodal_lme_rel"].min() >= 140.0 * 0.5 - 1e-6


def test_intra_ba_summary_reports_spread():
    p = _profile()
    lme = nodal.nodal_lme_index(p, 140.0)
    s = nodal.intra_ba_summary(p, lme, 140.0)
    assert s["n_nodes"] == 200
    assert s["n_congested_nodes"] > 0
    assert s["nodal_lme_max"] > s["nodal_lme_min"]
    assert s["congestion_spread_mean_dollar"] > 0
