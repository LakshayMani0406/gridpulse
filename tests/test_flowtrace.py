import numpy as np
import pandas as pd

from gridpulse import flowtrace as ft


def test_solver_matches_hand_computed_two_node():
    # A dirty (1000 kg/MWh) exports 50 to B (clean). B consumption = 333.33.
    P = np.array([100.0, 100.0])
    F = np.array([100000.0, 0.0])
    ID = np.array([[0.0, 50.0], [-50.0, 0.0]])
    r = ft.solve_consumption_rates(F, P, ID)
    assert abs(r[0] - 1000.0) < 1e-6
    assert abs(r[1] - 1000.0 * 50 / 150) < 1e-6


def test_isolated_node_safe():
    r = ft.solve_consumption_rates(np.array([5e4, 0.0]), np.array([50.0, 0.0]), np.zeros((2, 2)))
    assert abs(r[0] - 1000.0) < 1e-6 and r[1] == 0.0


def _network_fixture(n=120):
    periods = pd.date_range("2024-01-01", periods=n, freq="h")
    fuel, dem, ix = [], [], []
    imp = 400 + 100 * np.sin(np.arange(n) / 6)
    for t, im in zip(periods, imp):
        # A: coal generator; B: pure importer from A
        fuel.append({"period": t.isoformat(), "ba": "A", "fueltype": "COL", "mwh": 1000.0})
        fuel.append({"period": t.isoformat(), "ba": "B", "fueltype": "WND", "mwh": 200.0})
        dem.append({"period": t.isoformat(), "ba": "A", "mwh": 1000.0 - im})
        dem.append({"period": t.isoformat(), "ba": "B", "mwh": 200.0 + im})
        ix.append({"period": t.isoformat(), "from_ba": "A", "to_ba": "B", "mwh": float(im)})
        ix.append({"period": t.isoformat(), "from_ba": "B", "to_ba": "A", "mwh": float(-im)})
    return pd.DataFrame(fuel), pd.DataFrame(dem), pd.DataFrame(ix)


def test_consumption_rate_higher_than_production_for_importer():
    fuel, dem, ix = _network_fixture()
    ch = ft.consumption_hourly(fuel, ix, dem, ["A", "B"])
    fac = ft.consumption_factors(ch)
    b = fac[fac["ba"] == "B"].iloc[0]
    # B produces clean but imports coal -> consumption AEF >> production AEF (0)
    assert b["consumption_aef"] > b["production_aef"]
    assert b["consumption_aef"] > 100


def test_consumption_mef_runs_and_positive():
    fuel, dem, ix = _network_fixture()
    ch = ft.consumption_hourly(fuel, ix, dem, ["A", "B"])
    cm = ft.consumption_mef(ch, n_boot=50)
    assert "consumption_mef_kg_per_mwh" in cm.columns
    assert len(cm) >= 1
