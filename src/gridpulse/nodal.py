"""Thrust 2: intra-BA nodal marginal carbon (CAISO), from congestion.

Two sites in the *same* balancing authority can face different marginal carbon
because transmission congestion changes which generator serves the next MWh. We
show this for CAISO using the fully public OASIS feed (no auth), which decomposes
each node's LMP into energy (MCE), congestion (MCC), and loss (MCL). The
congestion component is a direct, published measure of intra-BA spatial variation.

We reuse the BA-level EIA-930 marginal emission factor (the system margin) and
modulate it by each node's persistent congestion to get a *directional, relative*
nodal marginal-carbon index: import-constrained nodes (positive congestion) are
served at the margin by more-expensive local units (typically gas -> higher
carbon); export-constrained nodes (negative congestion) sit on spilled local
renewables (lower carbon).

Honest limitation: an *exact* nodal kg/MWh needs generator shift factors + offer
stacks, which are CEII-restricted / proprietary (WattTime-REsurety, IOP 2024
doi:10.1088/2753-3751/ad72f6). What is reproducible from public data is the
congestion spread and the direction of the nodal adjustment.

CAISO OASIS: https://oasis.caiso.com/oasisapi/SingleZip (PRC_LMP).
"""
from __future__ import annotations

import io
import logging
import time
import zipfile

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("gridpulse.nodal")

OASIS = "https://oasis.caiso.com/oasisapi/SingleZip"


def fetch_caiso_nodal_day(date: str, market: str = "DAM", timeout: int = 120) -> pd.DataFrame:
    """All-APNode LMP components for one UTC day. `date` = 'YYYYMMDD'.

    Returns long rows (NODE, OPR_HR, LMP_TYPE, MW). Throttle callers to ~1/6s.
    """
    start = f"{date}T07:00-0000"
    # +1 day at 07:00 UTC (CAISO day boundary is local midnight = 07/08 UTC)
    end_dt = pd.Timestamp(date) + pd.Timedelta(days=1)
    end = f"{end_dt.strftime('%Y%m%d')}T07:00-0000"
    url = (f"{OASIS}?queryname=PRC_LMP&startdatetime={start}&enddatetime={end}"
           f"&version=1&market_run_id={market}&grp_type=ALL_APNODES&resultformat=6")
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    df = pd.read_csv(z.open(z.namelist()[0]))
    return df[["NODE", "OPR_HR", "LMP_TYPE", "MW"]]


def node_congestion_profile(days: list[str], market: str = "DAM",
                            throttle_s: float = 6.0) -> pd.DataFrame:
    """Per-node congestion statistics over representative days (aggregated small)."""
    frames = []
    for i, d in enumerate(days):
        try:
            df = fetch_caiso_nodal_day(d, market)
        except Exception as e:  # noqa: BLE001
            log.warning("CAISO fetch failed for %s: %s", d, str(e)[:80])
            continue
        mcc = df[df["LMP_TYPE"] == "MCC"][["NODE", "MW"]].rename(columns={"MW": "mcc"})
        mcc["day"] = d
        frames.append(mcc)
        log.info("CAISO %s: %d nodes", d, mcc["NODE"].nunique())
        if i < len(days) - 1:
            time.sleep(throttle_s)
    if not frames:
        return pd.DataFrame()
    allmcc = pd.concat(frames, ignore_index=True)
    prof = allmcc.groupby("NODE")["mcc"].agg(
        mcc_mean="mean", mcc_std="std", mcc_p10=lambda s: s.quantile(0.10),
        mcc_p90=lambda s: s.quantile(0.90), n="count").reset_index()
    return prof


def nodal_lme_index(profile: pd.DataFrame, system_mef: float,
                    sensitivity: float = 0.5) -> pd.DataFrame:
    """Directional nodal marginal-carbon index (kg/MWh) from congestion.

    LME_node = system_MEF * (1 + sensitivity * tanh(z(congestion))), bounded so a
    persistently import-constrained node reads above and an export-constrained node
    below the BA system margin. Relative/directional, not an exact nodal rate.
    """
    if profile.empty:
        return profile
    p = profile.copy()
    mu, sd = p["mcc_mean"].mean(), (p["mcc_mean"].std() or 1.0)
    z = (p["mcc_mean"] - mu) / sd
    p["nodal_lme_rel"] = system_mef * (1.0 + sensitivity * np.tanh(z))
    p["vs_system_pct"] = 100 * (p["nodal_lme_rel"] - system_mef) / system_mef
    return p.sort_values("nodal_lme_rel", ascending=False).reset_index(drop=True)


def intra_ba_summary(profile: pd.DataFrame, lme: pd.DataFrame, system_mef: float) -> dict:
    """Headline intra-BA numbers for FINDINGS."""
    congested = profile[profile["mcc_mean"].abs() > 1.0]
    return {
        "n_nodes": int(len(profile)),
        "n_congested_nodes": int(len(congested)),
        "congestion_spread_mean_dollar": float(profile["mcc_mean"].max() - profile["mcc_mean"].min()),
        "system_mef": float(system_mef),
        "nodal_lme_min": float(lme["nodal_lme_rel"].min()) if not lme.empty else float("nan"),
        "nodal_lme_max": float(lme["nodal_lme_rel"].max()) if not lme.empty else float("nan"),
        "nodal_lme_p10": float(lme["nodal_lme_rel"].quantile(0.10)) if not lme.empty else float("nan"),
        "nodal_lme_p90": float(lme["nodal_lme_rel"].quantile(0.90)) if not lme.empty else float("nan"),
    }
