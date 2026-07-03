import pandas as pd

from gridpulse import analysis as an


def _frames():
    mef = pd.DataFrame({
        "ba": ["HYDROX", "GASX", "COALX", "NUKEX"],
        # HYDROX looks cleanest on average but its extra MWh is gas/peakers -> dirty margin
        "mef_kg_per_mwh": [900.0, 469.0, 1000.0, 469.0],
        "ci_low": [880, 450, 980, 450], "ci_high": [920, 480, 1020, 480],
    })
    aef = pd.DataFrame({
        "ba": ["HYDROX", "GASX", "COALX", "NUKEX"],
        "aef_kg_per_mwh": [30.0, 350.0, 950.0, 60.0],  # HYDROX clean on avg, dirty on margin
    })
    return mef, aef


def test_annual_marginal_co2():
    # 100 MW at 500 kg/MWh for 8760h = 438,000 t
    assert abs(an.annual_marginal_co2(100, 500) - 438000.0) < 1e-6


def test_siting_index_columns_and_sort():
    mef, aef = _frames()
    s = an.siting_index(mef, aef, load_mw=100)
    assert {"rank_marginal", "rank_average", "rank_shift",
            "annual_co2_t_marginal", "avg_marginal_gap_kg"}.issubset(s.columns)
    # sorted ascending by MEF
    assert s["mef_kg_per_mwh"].is_monotonic_increasing


def test_rank_inversion_detected_for_hydro():
    mef, aef = _frames()
    s = an.siting_index(mef, aef, load_mw=100)
    inv = an.rank_inversions(s, top_k=2)
    # HYDROX is cleanest on average but ties others on margin -> flagged
    assert "HYDROX" in set(inv["ba"])


def test_siting_gap_positive_when_allocation_suboptimal():
    mef, aef = _frames()
    s = an.siting_index(mef, aef, load_mw=100)
    # put all load in the dirtiest region -> big gap vs optimal
    gap = an.siting_gap(s, {"COALX": 1.0}, load_mw_total=1000)
    assert gap["gap_mt_co2_yr"] > 0
    assert gap["best_mef"] <= s["mef_kg_per_mwh"].min() + 1e-9
