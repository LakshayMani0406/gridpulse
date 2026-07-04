import pandas as pd

from gridpulse import multiverse as mv


def _specs():
    # 5 BAs, 3 specs. A is robustly green, E robustly dirty, C flips hard.
    return {
        "spec1": pd.Series({"A": 10, "B": 100, "C": 20, "D": 300, "E": 900}),
        "spec2": pd.Series({"A": 15, "B": 200, "C": 500, "D": 250, "E": 800}),
        "spec3": pd.Series({"A": 5, "B": 150, "C": 600, "D": 280, "E": 950}),
    }


def test_spec_curve_ranks_and_verdicts():
    ranks, rob = mv.spec_curve(_specs())
    assert ranks.shape == (5, 3)
    # A always rank 1 -> robust-green; E always rank 5 -> robust-dirty
    assert rob.loc["A", "verdict"] == "robust-green"
    assert rob.loc["E", "verdict"] == "robust-dirty"
    # C ranges from 2 to 5 -> flips
    assert rob.loc["C", "verdict"] == "flips"
    assert rob.loc["C", "rank_range"] >= 2


def test_top_choice_stability():
    out = mv.top_choice_stability(_specs(), k=2)
    a = out[out["ba"] == "A"].iloc[0]
    assert a["top2_count"] == 3  # A in top-2 of all three specs
    assert abs(a["share_of_specs"] - 1.0) < 1e-9


def test_assemble_specifications_minimal(tmp_path):
    # tiny fuel/demand -> at least AEF + MEF specs present
    import numpy as np
    periods = pd.date_range("2024-01-01", periods=300, freq="h")
    rows, dem = [], []
    for i, t in enumerate(periods):
        g = 500 + 300 * np.sin(i / 12)
        rows.append({"period": t.isoformat(), "ba": "Z", "fueltype": "NG", "mwh": float(g)})
        rows.append({"period": t.isoformat(), "ba": "Z", "fueltype": "NUC", "mwh": 400.0})
        dem.append({"period": t.isoformat(), "ba": "Z", "mwh": float(g + 400)})
    specs = mv.assemble_specifications(pd.DataFrame(rows), pd.DataFrame(dem))
    assert "AEF (avg, prod, BA)" in specs
    assert "MEF short-run prod (regression)" in specs
