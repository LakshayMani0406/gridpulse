from pathlib import Path

import numpy as np
import pandas as pd

from gridpulse import robust

REPO = Path(__file__).resolve().parent.parent


def _toy():
    # 4 regions x 3 methods; A is best-or-tied on m1 & m3, B owns m2.
    return pd.DataFrame(
        {"m1": {"A": 10, "B": 20, "C": 30, "D": 40},
         "m2": {"A": 12, "B": 5, "C": 50, "D": 60},
         "m3": {"A": 8, "B": 40, "C": 9, "D": 70}}
    )


def test_regret_matrix_absolute_zero_at_optimum():
    reg = robust.regret_matrix(_toy(), "absolute")
    assert reg.loc["A", "m1"] == 0 and reg.loc["A", "m3"] == 0
    assert reg.loc["A", "m2"] == 7   # 12 - 5
    assert reg.loc["B", "m2"] == 0


def test_min_max_regret_site_is_A():
    mmr = robust.min_max_regret(_toy(), "absolute")
    assert mmr.index[0] == "A"
    assert mmr.loc["A", "max_regret"] == 7
    assert mmr.loc["A", "worst_method"] == "m2"
    assert robust.robust_site(_toy(), "absolute") == "A"


def test_price_of_robustness():
    p = robust.price_of_robustness(_toy(), "A", "absolute")
    assert p.iloc[0] == 7 and p["m2"] == 7
    assert p["m1"] == 0 and p["m3"] == 0


def test_low_regret_core():
    core = robust.low_regret_core(_toy(), eps=0.15, kind="normalized")
    assert core == ["A"]
    # loosening eps admits more regions
    assert set(robust.low_regret_core(_toy(), eps=1.0, kind="normalized")) == {"A", "B", "C", "D"}


def test_relative_regret_guards_nonpositive_optimum():
    f = pd.DataFrame({"m": {"A": 0.0, "B": 5.0, "C": 10.0}})  # optimum 0 -> relative undefined
    rel = robust.regret_matrix(f, "relative")
    assert rel["m"].isna().all()


def test_owa_minmax_matches_maxregret_and_average_is_mean():
    f = _toy()
    owa_mm = robust.owa_regret(f, "minmax", "absolute")
    assert owa_mm.index[0] == "A"
    assert owa_mm.loc["A", "owa_regret"] == 7
    owa_avg = robust.owa_regret(f, "average", "absolute")
    assert abs(owa_avg.loc["A", "owa_regret"] - 7 / 3) < 1e-9


def test_hedge_pair_perfectly_complementary():
    hp = robust.hedge_pairs(_toy(), top=3)
    top = hp.iloc[0]
    assert {top["ba_a"], top["ba_b"]} == {"A", "B"}   # A+B cover every method's optimum
    assert top["pair_max_regret"] == 0
    assert top["rank_corr"] < 0                        # anti-correlated -> a real hedge


# --------------------------------------------------------------- real committed data
def test_real_min_max_regret_is_pacific_nw():
    f = robust.load_factor_matrix(REPO / "data" / "multiverse_factors.csv")
    assert robust.AEF_COL not in f.columns  # marginal set by default (AEF excluded)
    r = robust.robust_site(f, "absolute")
    assert r == "BPAT"                                   # formalises the Pacific-NW result
    core = robust.low_regret_core(f, eps=0.10, kind="normalized")
    assert "BPAT" in core and set(core) <= {"BPAT", "PACW"}


# --------------------------------------------------------------- 10x: uncertainty
def _assembled_two_bas(n=500):
    """Two BAs with clean planted margins (NG-marginal), for MEF draws."""
    from gridpulse import emissions as em
    rng = np.random.default_rng(0)
    periods = pd.date_range("2024-01-01", periods=n, freq="h")
    rows = []
    for ba in ("T1", "T2"):
        marg = np.clip(3000 + 2000 * np.sin(np.arange(n) / 12) + rng.normal(0, 150, n), 0, None)
        for t, g in zip(periods, marg):
            rows.append({"period": t.isoformat(), "ba": ba, "fueltype": "NUC", "mwh": 5000.0})
            rows.append({"period": t.isoformat(), "ba": ba, "fueltype": "NG", "mwh": float(g)})
    hc = em.hourly_co2(pd.DataFrame(rows))
    dem = hc[["period", "ba", "gen_mwh"]].rename(columns={"gen_mwh": "demand_mwh"})
    return hc.merge(dem, on=["ba", "period"])


def test_mef_estimation_draws_bootstrap_and_bayesian():
    from gridpulse.regions import factor_for
    asm = _assembled_two_bas()
    boot = robust.mef_estimation_draws(asm, n_draws=100, method="bootstrap", seed=1)
    bayes = robust.mef_estimation_draws(asm, n_draws=100, method="bayesian", seed=1)
    assert boot.shape == (100, 2) and set(boot.columns) == {"T1", "T2"}
    assert bayes.shape == (100, 2)
    # both center near the planted NG marginal factor
    assert abs(boot["T1"].mean() - factor_for("NG")) < 25
    assert abs(bayes["T1"].mean() - factor_for("NG")) < 25


def test_robust_site_survives_estimation_uncertainty():
    reg = "MEF short-run prod (regression)"
    # A dominates on the non-regression methods regardless of its regression draw
    f = pd.DataFrame({
        reg: {"A": 10.0, "B": 50.0, "C": 90.0},
        "other1": {"A": 1.0, "B": 100.0, "C": 200.0},
        "other2": {"A": 2.0, "B": 120.0, "C": 220.0},
    })
    rng = np.random.default_rng(0)
    draws = pd.DataFrame({"A": rng.uniform(8, 12, 50),
                          "B": rng.uniform(48, 52, 50),
                          "C": rng.uniform(88, 92, 50)})
    out = robust.robust_site_under_uncertainty(f, draws, regression_col=reg)
    assert out["point_site"] == "A"
    assert out["p_point_site_is_robust"] == 1.0
    dr = robust.distributionally_robust_site(f, draws, regression_col=reg)
    assert dr["dr_site"] == "A"
    assert dr["n_scenarios"] == 2 + 50  # 2 point methods + 50 regression draws
