"""EIA API v2 client: retry, pagination, and an on-disk page cache.

The client speaks the EIA v2 ``/data`` protocol (offset pagination, faceted
filters). Responses are cached to ``data/cache`` keyed by a hash of the request
(api key excluded) so backfills are idempotent and cheap to re-run.

Docs: https://www.eia.gov/opendata/documentation/
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

from .config import Config

log = logging.getLogger("gridpulse.ingest")

BASE = "https://api.eia.gov/v2"

# Route paths.
ROUTE_FUEL = "electricity/rto/fuel-type-data"
ROUTE_REGION = "electricity/rto/region-data"
ROUTE_INTERCHANGE = "electricity/rto/interchange-data"
ROUTE_RETAIL = "electricity/retail-sales"


@dataclass
class EIAClient:
    cfg: Config
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": "gridpulse/0.1 (+research)"})
        self.cfg.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ cache
    def _cache_path(self, route: str, params: dict[str, Any]) -> Path:
        # Exclude api_key from the cache key so keys don't leak into filenames
        # and different keys share the same cache.
        keyless = {k: v for k, v in params.items() if k != "api_key"}
        blob = route + "?" + json.dumps(keyless, sort_keys=True, default=str)
        h = hashlib.sha256(blob.encode()).hexdigest()[:20]
        safe = route.replace("/", "_")
        return self.cfg.cache_dir / f"{safe}_{h}.json"

    # ------------------------------------------------------------------ http
    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET with exponential backoff on 429/5xx and transient errors."""
        assert self.session is not None
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                r = self.session.get(url, params=params, timeout=self.cfg.request_timeout)
                if r.status_code == 200:
                    body = r.json()
                    if "response" not in body:
                        raise ValueError(f"EIA API error: {body.get('error', body)}")
                    return body["response"]
                if r.status_code in (429, 500, 502, 503, 504):
                    log.warning("EIA %s (attempt %d/%d), backing off %.1fs",
                                r.status_code, attempt, self.cfg.max_retries, delay)
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                r.raise_for_status()
            except (requests.RequestException, ValueError) as e:
                last_exc = e
                log.warning("request failed (attempt %d/%d): %s", attempt, self.cfg.max_retries, e)
                time.sleep(delay)
                delay = min(delay * 2, 30)
        raise RuntimeError(f"EIA request failed after {self.cfg.max_retries} retries: {last_exc}")

    # ------------------------------------------------------- paginated fetch
    def fetch(
        self,
        route: str,
        data_cols: list[str],
        facets: dict[str, list[str]] | None = None,
        frequency: str = "hourly",
        start: str | None = None,
        end: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch a full (paginated) result set from an EIA v2 data route."""
        assert self.cfg.has_key, "EIA_API_KEY is required for live fetch"
        params: dict[str, Any] = {
            "api_key": self.cfg.eia_api_key,
            "frequency": frequency,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": self.cfg.page_length,
        }
        for i, c in enumerate(data_cols):
            params[f"data[{i}]"] = c
        if facets:
            for fname, vals in facets.items():
                params[f"facets[{fname}][]"] = list(vals)

        cache_file = self._cache_path(route, params)
        if use_cache and cache_file.exists():
            records = json.loads(cache_file.read_text())
            log.debug("cache hit %s (%d rows)", cache_file.name, len(records))
            return pd.DataFrame(records)

        url = f"{BASE}/{route}/data/"
        all_records: list[dict] = []
        offset = 0
        total = None
        while True:
            params["offset"] = offset
            resp = self._get(url, params)
            recs = resp.get("data", [])
            if total is None:
                total = int(resp.get("total", 0))
                log.info("%s %s..%s: %d rows across %d BA", route, start, end, total,
                         len(facets.get("respondent", [])) if facets else 0)
            all_records.extend(recs)
            if not recs or len(all_records) >= total:
                break
            offset += len(recs)

        if use_cache:
            cache_file.write_text(json.dumps(all_records))
        return pd.DataFrame(all_records)

    # ---------------------------------------------------------- typed pulls
    def fuel_type(self, bas: Iterable[str], start: str, end: str, **kw) -> pd.DataFrame:
        df = self.fetch(ROUTE_FUEL, ["value"], {"respondent": list(bas)},
                        start=start, end=end, **kw)
        return _tidy(df, ["period", "respondent", "fueltype", "value"])

    def demand(self, bas: Iterable[str], start: str, end: str, **kw) -> pd.DataFrame:
        df = self.fetch(ROUTE_REGION, ["value"],
                        {"respondent": list(bas), "type": ["D"]},
                        start=start, end=end, **kw)
        return _tidy(df, ["period", "respondent", "value"])

    def interchange(self, from_bas: Iterable[str], start: str, end: str, **kw) -> pd.DataFrame:
        df = self.fetch(ROUTE_INTERCHANGE, ["value"], {"fromba": list(from_bas)},
                        start=start, end=end, **kw)
        return _tidy(df, ["period", "fromba", "toba", "value"])

    def retail_sales(self, states: Iterable[str], start: str, end: str, **kw) -> pd.DataFrame:
        df = self.fetch(ROUTE_RETAIL, ["sales"],
                        {"stateid": list(states), "sectorid": ["ALL"]},
                        frequency="monthly", start=start, end=end, **kw)
        return _tidy(df, ["period", "stateid", "sales"], value_cols=["sales"])


def _tidy(df: pd.DataFrame, keep: list[str], value_cols: tuple[str, ...] | list[str] = ("value",)) -> pd.DataFrame:
    """Keep expected columns, coerce numeric value columns, drop empties."""
    if df.empty:
        return pd.DataFrame(columns=keep)
    for c in keep:
        if c not in df.columns:
            df[c] = pd.NA
    out = df[keep].copy()
    for vc in value_cols:
        if vc in out.columns:
            out[vc] = pd.to_numeric(out[vc], errors="coerce")
    return out.dropna(subset=list(value_cols)).reset_index(drop=True)
