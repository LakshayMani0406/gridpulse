import pandas as pd
import pytest

from gridpulse.config import load_config
from gridpulse.storage import Warehouse


@pytest.fixture
def wh(tmp_path, monkeypatch):
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path / "data"))
    cfg = load_config()
    return Warehouse(cfg)


def _demand_rows(periods, ba="CISO", val=100.0):
    return pd.DataFrame({"period": periods, "ba": ba, "mwh": [val] * len(periods)})


def test_upsert_and_count(wh):
    df = _demand_rows(["2024-01-01T00", "2024-01-01T01"])
    n = wh.upsert("demand", df)
    assert n == 2
    assert wh.count("demand") == 2


def test_upsert_is_idempotent(wh):
    df = _demand_rows(["2024-01-01T00", "2024-01-01T01"])
    wh.upsert("demand", df)
    wh.upsert("demand", df)  # same keys again
    assert wh.count("demand") == 2  # no duplication


def test_upsert_updates_value_on_conflict(wh):
    wh.upsert("demand", _demand_rows(["2024-01-01T00"], val=100.0))
    wh.upsert("demand", _demand_rows(["2024-01-01T00"], val=250.0))
    back = wh.read("demand")
    assert len(back) == 1
    assert float(back["mwh"].iloc[0]) == 250.0


def test_watermark_advances(wh):
    wh.upsert("demand", _demand_rows(["2024-01-01T00", "2024-01-01T05"]))
    assert wh.watermark("demand") == "2024-01-01T05"
    wh.upsert("demand", _demand_rows(["2024-02-01T00"]))
    assert wh.watermark("demand") == "2024-02-01T00"


def test_manifest_records_rows(wh):
    wh.upsert("demand", _demand_rows(["2024-01-01T00"]))
    man = wh.load_manifest()
    assert "demand" in man and man["demand"]["watermark"] == "2024-01-01T00"


def test_read_missing_table_empty(wh):
    assert wh.read("interchange").empty


def test_rebuild_manifest_from_data(wh):
    wh.upsert("demand", _demand_rows(["2024-01-01T00", "2024-01-01T05"], ba="CISO"))
    wh.upsert("demand", _demand_rows(["2024-03-01T00"], ba="BPAT"))
    # clobber the manifest with a stale/foreign value, then rebuild from data
    wh.cfg.manifest_path.write_text('{"demand": {"watermark": "1999-01-01T00", '
                                    '"watermark_by_ba": {"XXXX": "1999-01-01T00"}}}')
    man = wh.rebuild_manifest()
    assert man["demand"]["watermark"] == "2024-03-01T00"
    assert man["demand"]["watermark_by_ba"] == {"CISO": "2024-01-01T05", "BPAT": "2024-03-01T00"}


def test_per_ba_watermark_tracks_each_ba(wh):
    wh.upsert("demand", _demand_rows(["2024-01-01T00", "2024-01-01T05"], ba="CISO"))
    wh.upsert("demand", _demand_rows(["2024-03-01T00"], ba="BPAT"))
    by = wh.watermark_by_ba("demand")
    assert by["CISO"] == "2024-01-01T05"
    assert by["BPAT"] == "2024-03-01T00"
    # a subset pull for one BA must not overwrite the other's coverage
    wh.upsert("demand", _demand_rows(["2024-02-01T00"], ba="CISO"))
    assert wh.watermark_by_ba("demand")["BPAT"] == "2024-03-01T00"
