"""Weather features for demand forecasting: heating/cooling degree days.

Electricity demand is driven by temperature (AC in summer, heating in winter).
We add cooling/heating degree-hours per BA and re-run the backtest to measure
the forecast-skill gain over the calendar+lag model.

Hourly 2 m temperature comes from the Open-Meteo historical archive (ERA5
reanalysis; free, no API key), fetched for each BA's representative load center
and cached to disk. Degree days use the standard 65 degF base.
"""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config
from .regions import REGIONS

log = logging.getLogger("gridpulse.weather")

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
BASE_F = 65.0  # degree-day base temperature (deg F)


def _cache_file(cfg: Config, lat: float, lon: float, start: str, end: str) -> Path:
    key = hashlib.sha256(f"{lat}_{lon}_{start}_{end}".encode()).hexdigest()[:16]
    d = cfg.cache_dir / "weather"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"om_{key}.json"


def fetch_hourly_temp(cfg: Config, lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """Hourly temperature (deg F) for a point over [start, end] (dates YYYY-MM-DD)."""
    cf = _cache_file(cfg, lat, lon, start, end)
    if cf.exists():
        data = json.loads(cf.read_text())
    else:
        url = (f"{ARCHIVE}?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
               "&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=UTC")
        req = urllib.request.Request(url, headers={"User-Agent": "gridpulse/0.1"})
        with urllib.request.urlopen(req, timeout=cfg.request_timeout) as r:
            data = json.load(r)
        cf.write_text(json.dumps(data))
    h = data.get("hourly", {})
    if not h:
        return pd.DataFrame(columns=["period", "temp_f"])
    return pd.DataFrame({"period": pd.to_datetime(h["time"]), "temp_f": h["temperature_2m"]})


def attach_weather(cfg: Config, series: pd.DataFrame, ba: str) -> pd.DataFrame:
    """Merge temperature + degree-hour features onto a BA demand series."""
    reg = REGIONS.get(ba)
    if reg is None:
        return series.assign(temp_f=np.nan, cdh=np.nan, hdh=np.nan)
    s = series.copy()
    s["period"] = pd.to_datetime(s["period"])
    start = s["period"].min().strftime("%Y-%m-%d")
    end = s["period"].max().strftime("%Y-%m-%d")
    temp = fetch_hourly_temp(cfg, reg.lat, reg.lon, start, end)
    if temp.empty:
        return s.assign(temp_f=np.nan, cdh=np.nan, hdh=np.nan)
    s = s.merge(temp, on="period", how="left")
    s["temp_f"] = s["temp_f"].interpolate().ffill().bfill()
    s["cdh"] = (s["temp_f"] - BASE_F).clip(lower=0)   # cooling degree-hours
    s["hdh"] = (BASE_F - s["temp_f"]).clip(lower=0)   # heating degree-hours
    return s


WEATHER_FEATURES = ["temp_f", "cdh", "hdh"]
