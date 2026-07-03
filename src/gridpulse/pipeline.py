"""End-to-end orchestration: offline (synthetic) and live incremental pull.

``run_offline`` needs no network/key; ``run_live`` pulls incrementally from the
EIA API using the warehouse watermark and computes real AEF/MEF/siting. Both
produce charts and a markdown report (offline figures are watermarked).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

from . import analysis, emissions, reporting
from .config import Config, load_config, setup_logging
from .ingest import EIAClient
from .regions import REGION_CODES
from .storage import Warehouse
from .synthetic import make_fixture

log = logging.getLogger("gridpulse.pipeline")

# State abbreviations per BA, for retail-sales pulls (best-effort primary state).
BA_STATE = {
    "CISO": "CA", "LDWP": "CA", "BANC": "CA", "ERCO": "TX", "PJM": "PA", "MISO": "IL",
    "SWPP": "KS", "ISNE": "MA", "NYIS": "NY", "BPAT": "OR", "PACW": "OR", "PACE": "UT",
    "PSCO": "CO", "PNM": "NM", "AZPS": "AZ", "SRP": "AZ", "NEVP": "NV", "PGE": "OR",
    "IPCO": "ID", "WACM": "CO", "SOCO": "GA", "TVA": "TN", "DUK": "NC", "CPLE": "NC",
    "FPL": "FL", "FPC": "FL", "LGEE": "KY", "AECI": "MO",
}


@dataclass
class PipelineResult:
    aef: pd.DataFrame
    mef: pd.DataFrame
    siting: pd.DataFrame
    inversions: pd.DataFrame
    synthetic: bool
    report_path: str | None = None
    figures: list[str] = field(default_factory=list)
    n_rows: dict = field(default_factory=dict)


# ---------------------------------------------------------------- compute core
def _compute(fuel_long: pd.DataFrame, demand_long: pd.DataFrame, cfg: Config,
             synthetic: bool, load_mw: float = 100.0, driver: str = "demand") -> PipelineResult:
    assembled = emissions.assemble_hourly(fuel_long, demand_long)
    aef = emissions.aef_by_ba(assembled)
    mef = emissions.mef_by_ba(assembled, driver=driver)
    siting = analysis.siting_index(mef, aef, load_mw=load_mw)
    inversions = analysis.rank_inversions(siting)

    figs: list[str] = []
    cfg.ensure_dirs()
    p1 = reporting.chart_aef_vs_mef(siting, cfg.figs_dir / "aef_vs_mef.png", synthetic)
    p2 = reporting.chart_rank_scatter(siting, cfg.figs_dir / "rank_scatter.png", synthetic)
    figs += [str(p) for p in (p1, p2) if p]
    rp = reporting.build_report(siting, inversions, cfg.repo_root / "docs" / "report.md", synthetic)
    return PipelineResult(aef, mef, siting, inversions, synthetic, str(rp), figs)


# -------------------------------------------------------------------- offline
def run_offline(cfg: Config | None = None) -> PipelineResult:
    cfg = cfg or load_config()
    setup_logging(cfg.log_level)
    log.info("running OFFLINE (synthetic fixture)")
    fuel_long, demand_long = make_fixture()
    return _compute(fuel_long, demand_long, cfg, synthetic=True)


# ------------------------------------------------------------- incremental IO
def _months_between(start: datetime, end: datetime):
    """Yield (start_str, end_str) hourly windows, one per calendar month."""
    cur = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while cur <= end:
        nxt = datetime(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1, tzinfo=timezone.utc)
        w_start = max(cur, start)
        w_end = min(nxt - timedelta(hours=1), end)
        yield w_start.strftime("%Y-%m-%dT%H"), w_end.strftime("%Y-%m-%dT%H")
        cur = nxt


def incremental_pull(cfg: Config, wh: Warehouse, months: int | None = None,
                     bas: list[str] | None = None,
                     interchange_months: int | None = None) -> dict:
    """Pull only periods newer than each dataset's watermark; idempotent upsert.

    ``interchange_months`` optionally caps the interchange window (it is far
    larger than the other tables and flow-tracing needs only a representative
    span); ``None`` uses the same window as everything else.
    """
    client = EIAClient(cfg)
    bas = bas or REGION_CODES
    months = months or cfg.backfill_months
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    default_start = now - timedelta(days=30 * months)
    ix_default_start = now - timedelta(days=30 * (interchange_months or months))
    counts: dict[str, int] = {}

    def window_for(table: str, entities: list[str], dflt: datetime | None = None) -> datetime:
        """Start = earliest point needed to cover every requested entity.

        Uses the per-entity watermark so a subset pull (or a lagging BA) can't
        leave gaps: any entity with no data yet forces the full backfill window;
        otherwise start just after the least-covered entity. Idempotent upserts
        make the (cheap, cached) overlap for already-covered entities a no-op.
        """
        base = dflt or default_start
        by = wh.watermark_by_ba(table)
        if not entities or any(e not in by for e in entities):
            return base
        earliest = min(pd.to_datetime(by[e]) for e in entities)
        return max(base, earliest.to_pydatetime().replace(tzinfo=timezone.utc) + timedelta(hours=1))

    # fuel mix
    start = window_for("fuel_mix", bas)
    for w0, w1 in _months_between(start, now):
        df = client.fuel_type(bas, w0, w1)
        if not df.empty:
            df = df.rename(columns={"respondent": "ba", "value": "mwh"})
            counts["fuel_mix"] = wh.upsert("fuel_mix", df[["period", "ba", "fueltype", "mwh"]])
    # demand
    start = window_for("demand", bas)
    for w0, w1 in _months_between(start, now):
        df = client.demand(bas, w0, w1)
        if not df.empty:
            df = df.rename(columns={"respondent": "ba", "value": "mwh"})
            counts["demand"] = wh.upsert("demand", df[["period", "ba", "mwh"]])
    # interchange (for Phase B; pulled here so the warehouse is complete)
    start = window_for("interchange", bas, dflt=ix_default_start)
    for w0, w1 in _months_between(start, now):
        df = client.interchange(bas, w0, w1)
        if not df.empty:
            df = df.rename(columns={"value": "mwh"})
            counts["interchange"] = wh.upsert("interchange", df[["period", "fromba", "toba", "mwh"]]
                                              .rename(columns={"fromba": "from_ba", "toba": "to_ba"}))
    # retail sales (monthly)
    states = sorted({BA_STATE[b] for b in bas if b in BA_STATE})
    rs_start = window_for("retail_sales", states)
    df = client.retail_sales(states, rs_start.strftime("%Y-%m"), now.strftime("%Y-%m"))
    if not df.empty:
        df = df.rename(columns={"stateid": "state", "sales": "sales_gwh"})
        counts["retail_sales"] = wh.upsert("retail_sales", df[["period", "state", "sales_gwh"]])
    return counts


# ------------------------------------------------------------------- live run
def run_live(cfg: Config | None = None, months: int | None = None,
             bas: list[str] | None = None, load_mw: float = 100.0) -> PipelineResult:
    cfg = cfg or load_config()
    setup_logging(cfg.log_level)
    if not cfg.has_key:
        raise RuntimeError("EIA_API_KEY missing; set it in .env for a live run")
    wh = Warehouse(cfg)
    log.info("running LIVE incremental pull (%d months, %d BAs, backend=%s)",
             months or cfg.backfill_months, len(bas or REGION_CODES), wh.backend)
    counts = incremental_pull(cfg, wh, months=months, bas=bas)

    fuel = wh.read("fuel_mix").rename(columns={"mwh": "mwh"})
    demand = wh.read("demand")
    fuel_long = fuel.rename(columns={"ba": "ba"})[["period", "ba", "fueltype", "mwh"]]
    demand_long = demand[["period", "ba", "mwh"]]
    res = _compute(fuel_long, demand_long, cfg, synthetic=False, load_mw=load_mw)
    res.n_rows = counts
    # export parquet snapshots for portability / CI artifacts
    for t in ("fuel_mix", "demand", "interchange", "retail_sales"):
        wh.export_parquet(t)
    return res


def run_now(cfg: Config | None = None, **kw) -> PipelineResult:
    """Live if a key is present, else offline."""
    cfg = cfg or load_config()
    return run_live(cfg, **kw) if cfg.has_key else run_offline(cfg)
