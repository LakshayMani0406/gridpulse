import pandas as pd

from gridpulse.config import load_config
from gridpulse.ingest import _tidy
from gridpulse.regions import REGION_CODES, factor_for, FOSSIL_FUELS, CLEAN_FUELS
from gridpulse.synthetic import make_fixture, planted_mef


def test_regions_nonempty_and_diverse():
    assert len(REGION_CODES) >= 20
    assert "CISO" in REGION_CODES and "ERCO" in REGION_CODES and "BPAT" in REGION_CODES


def test_factor_defaults_and_fossil_split():
    assert factor_for("COL") > factor_for("NG") > 0
    assert factor_for("NUC") == 0.0  # EIA production basis
    assert FOSSIL_FUELS.isdisjoint(CLEAN_FUELS)


def test_tidy_coerces_and_drops_na():
    raw = pd.DataFrame([
        {"period": "2024-01-01T00", "respondent": "CISO", "fueltype": "NG", "value": "123"},
        {"period": "2024-01-01T00", "respondent": "CISO", "fueltype": "COL", "value": None},
    ])
    out = _tidy(raw, ["period", "respondent", "fueltype", "value"])
    assert len(out) == 1
    assert out["value"].iloc[0] == 123.0


def test_synthetic_fixture_shape():
    fuel, demand = make_fixture(hours=100)
    assert set(fuel.columns) == {"period", "ba", "fueltype", "mwh"}
    assert set(demand.columns) == {"period", "ba", "mwh"}
    assert demand["mwh"].min() > 0


def test_planted_mef_values():
    assert planted_mef("COALX") == factor_for("COL")
    assert planted_mef("GASX") == factor_for("NG")


def test_run_offline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path / "data"))
    from gridpulse.pipeline import run_offline
    cfg = load_config()
    res = run_offline(cfg)
    assert res.synthetic is True
    assert len(res.siting) == 4
    assert res.report_path and (cfg.repo_root / "docs" / "report.md").exists()
    # marginal and average rankings should not be identical (inversion exists)
    assert (res.siting["rank_shift"] != 0).any()
