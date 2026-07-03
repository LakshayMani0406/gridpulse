import pandas as pd

from gridpulse import siting as st


def test_facility_to_ba_nearest_loadcenter():
    # A facility near Phoenix should map to an Arizona BA (AZPS/SRP).
    row = pd.Series({"lat": 33.4, "lon": -112.0, "mw": 50})
    assert st.facility_to_ba(row) in {"AZPS", "SRP"}


def test_facility_to_ba_by_state():
    row = pd.Series({"lat": None, "lon": None, "state": "TX", "mw": 100})
    assert st.facility_to_ba(row) == "ERCO"


def test_allocate_facilities_shares_sum_to_one():
    facs = pd.DataFrame({
        "lat": [33.4, 36.7, 31.0], "lon": [-112.0, -119.7, -99.0], "mw": [100, 200, 300],
    })
    alloc = st.allocate_facilities(facs)
    assert abs(alloc["share"].sum() - 1.0) < 1e-9
    assert alloc["total_mw"].sum() == 600


def _rankings():
    aef = pd.DataFrame({"ba": ["X", "Y", "Z"], "aef_kg_per_mwh": [50.0, 400.0, 900.0]})
    prod = pd.DataFrame({"ba": ["X", "Y", "Z"], "mef_kg_per_mwh": [800.0, 469.0, 950.0]})
    cons = pd.DataFrame({"ba": ["X", "Y", "Z"], "consumption_mef_kg_per_mwh": [850.0, 469.0, 950.0]})
    return aef, prod, cons


def test_combined_ranking_detects_rerank():
    aef, prod, cons = _rankings()
    r = st.combined_ranking(aef, prod, cons)
    # X is best on AEF (rank 1) but worst-ish on consumption MEF -> negative rerank
    x = r[r["ba"] == "X"].iloc[0]
    assert x["rank_aef"] == 1
    assert x["rerank_aef_to_cons"] < 0


def test_actual_vs_optimal_gap_positive():
    aef, prod, cons = _rankings()
    r = st.combined_ranking(aef, prod, cons)
    alloc = pd.DataFrame({"ba": ["X", "Z"], "total_mw": [500, 500], "share": [0.5, 0.5]})
    gap = st.actual_vs_optimal(r, alloc, total_new_mw=1000)
    assert gap["gap_mt_co2_yr"] > 0
    assert gap["best_ba"] == "Y"  # lowest consumption MEF


def test_constrained_optimal_between_unconstrained_and_actual():
    aef, prod, cons = _rankings()
    r = st.combined_ranking(aef, prod, cons)
    alloc = pd.DataFrame({"ba": ["X", "Z"], "total_mw": [500, 500], "share": [0.5, 0.5]})
    # Y (cleanest) can only absorb 400 MW; rest must spill to dirtier BAs.
    cap = {"Y": 400.0, "X": 400.0, "Z": 400.0}
    gap = st.actual_vs_optimal(r, alloc, total_new_mw=1000, capacity_mw=cap)
    # constrained optimum is worse than unconstrained but still better than actual
    assert (gap["optimal_unconstrained_mt_co2_yr"]
            <= gap["optimal_constrained_mt_co2_yr"]
            <= gap["actual_mt_co2_yr"])
    assert 0 < gap["gap_constrained_mt_co2_yr"] <= gap["gap_unconstrained_mt_co2_yr"]
    assert sum(gap["constrained_placement_mw"].values()) <= 1000
