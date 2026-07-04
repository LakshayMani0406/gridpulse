"""NREL Cambium long-run marginal emission rates (LRMER), by balancing authority.

Cambium publishes LRMER (kg CO2e/MWh) at 18 GEA regions for forward years
(2025, 2030, ... 2050) under multiple scenarios. LRMER captures the *long-run*
marginal response (induced capacity) that a 15+ year data center actually drives,
versus the short-run dispatch margin our Siler-Evans MEF measures.

Source: NREL Cambium 2024 (Gagnon et al.), https://www.nrel.gov/analysis/cambium.html
via the Scenario Viewer API (ready ``lrmer_co2e`` column). We hit the canonical
``scenarioviewer.nrel.gov`` first and fall back to alternate hosts if DNS is
rewritten (some sandboxes alias nrel.gov). GEA->BA crosswalk from the Cambium
workbook County Mapping tab; multi-GEA BAs are averaged over their GEAs.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile

import pandas as pd
import requests

log = logging.getLogger("gridpulse.cambium")

# Canonical host first; alternates cover sandbox DNS rewrites.
SV_HOSTS = ["https://scenarioviewer.nrel.gov", "https://scenarioviewer.nlr.gov"]
CAMBIUM_2024 = "5c7bef16-7e38-4094-92ce-8b03dfa93380"
CAMBIUM_2023 = "0f92fe57-3365-428a-8fe8-0afc326b3b43"

# EIA-930 BA -> Cambium GEA region(s). Multi-GEA BAs are averaged (approx; a
# load-weighted split would use EIA-861 footprints). From the Cambium workbook.
BA_TO_GEA: dict[str, list[str]] = {
    "CISO": ["CAISO"], "LDWP": ["CAISO"], "ERCO": ["ERCOT"], "ISNE": ["ISONE"],
    "NYIS": ["NYISO"], "PJM": ["PJM_East", "PJM_West"],
    "MISO": ["MISO_North", "MISO_Central", "MISO_South"],
    "SWPP": ["SPP_North", "SPP_South"], "SOCO": ["SERTP"], "TVA": ["SERTP"],
    "DUK": ["SERTP"], "CPLE": ["SERTP"], "FPL": ["FRCC"], "FPC": ["FRCC"],
    "PSCO": ["WestConnect_North"], "AZPS": ["WestConnect_South"],
    "SRP": ["WestConnect_South"], "PNM": ["WestConnect_South"],
    "BPAT": ["NorthernGrid_West"], "PACW": ["NorthernGrid_West"],
    "PGE": ["NorthernGrid_West"], "IPCO": ["NorthernGrid_East"],
    "NEVP": ["NorthernGrid_South"], "PACE": ["NorthernGrid_South", "NorthernGrid_East"],
    "WACM": ["WestConnect_North"], "AECI": ["SPP_South"], "LGEE": ["PJM_East"],
}

_METRIC_LRMER = "LRMER: CO2e Combustion+Precombustion [kg/MWh]"
_METRIC_SRMER = "SRMER: CO2e Combustion+Precombustion [kg/MWh]"


def _session_host() -> tuple[requests.Session, str]:
    last = None
    for host in SV_HOSTS:
        try:
            s = requests.Session()
            r = s.get(f"{host}/?project={CAMBIUM_2024}&mode=download", timeout=30)
            r.raise_for_status()
            if "csrftoken" in s.cookies:
                return s, host
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    raise RuntimeError(f"could not reach any Cambium Scenario Viewer host: {last}")


def fetch_cambium_metric(uuid: str = CAMBIUM_2024, scenario: str = "Mid-case",
                         year: str = "2025", metric: str = _METRIC_LRMER) -> pd.DataFrame:
    """Annual GEA-region table with the requested Cambium metric (kg CO2e/MWh)."""
    s, host = _session_host()
    hdr = {"X-CSRFToken": s.cookies.get("csrftoken", ""), "Referer": f"{host}/"}
    inputs = {"scenario": scenario, "technology": "ALL", "technology_type": "Technologies",
              "location": "ALL", "location_type": "GEA Regions 2023", "year": year,
              "metric": metric, "scenario_diff": None}
    fid = s.post(f"{host}/api/download_data/",
                 data={"project_uuid": uuid, "inputs": json.dumps(inputs), "x_axis": "annual"},
                 headers=hdr, timeout=60).json()["file_ids"]
    blob = s.post(f"{host}/api/download/", data={"file_ids": fid, "project_uuid": uuid},
                  headers=hdr, timeout=120).content
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
        raw, skip = zf.read(zf.namelist()[0]), 5
    except zipfile.BadZipFile:
        raw, skip = blob, 0
    df = pd.read_csv(io.BytesIO(raw), skiprows=skip)
    log.info("Cambium %s %s %s via %s: %d rows", uuid[:8], scenario, year, host, len(df))
    return df


def lrmer_by_ba(scenario: str = "Mid-case", years: tuple[int, ...] = (2025, 2030),
                uuid: str = CAMBIUM_2024, metric: str = _METRIC_LRMER) -> pd.Series:
    """LRMER (kg CO2e/MWh) per EIA BA, averaged over ``years`` and the BA's GEAs.

    Averaging 2025+2030 approximates the near-term levelized long-run margin a
    facility built now would see. Returns a Series indexed by BA code.
    """
    frames = []
    for y in years:
        df = fetch_cambium_metric(uuid=uuid, scenario=scenario, year=str(y), metric=metric)
        col = "lrmer_co2e" if "lrmer_co2e" in df.columns else _value_col(df)
        frames.append(df[["gea", col]].rename(columns={col: "val"}).assign(year=y))
    ally = pd.concat(frames, ignore_index=True)
    gea_mean = ally.groupby("gea")["val"].mean()
    out = {}
    for ba, geas in BA_TO_GEA.items():
        vals = [gea_mean[g] for g in geas if g in gea_mean.index]
        if vals:
            out[ba] = float(sum(vals) / len(vals))
    return pd.Series(out, name="lrmer_co2e")


def _value_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if c.lower().startswith("lrmer") or c.lower().startswith("srmer"):
            return c
    # last numeric column as a fallback
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return num[-1]
