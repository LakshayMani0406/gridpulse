"""Warehouse: DuckDB(+Parquet) with a CSV fallback, plus an incremental manifest.

The manifest records, per dataset, the latest period successfully ingested (a
"watermark"). The monthly refresh reads the watermark and only pulls new
periods; upserts are idempotent (delete-overlap then insert) so re-running a
window never double-counts.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

from .config import Config, WAREHOUSE_BACKEND

log = logging.getLogger("gridpulse.storage")

# Canonical table schemas: table -> (key columns, value columns).
SCHEMAS: dict[str, dict] = {
    "fuel_mix": {"keys": ["period", "ba", "fueltype"], "values": ["mwh"], "time": "period"},
    "demand": {"keys": ["period", "ba"], "values": ["mwh"], "time": "period"},
    "interchange": {"keys": ["period", "from_ba", "to_ba"], "values": ["mwh"], "time": "period"},
    "retail_sales": {"keys": ["period", "state"], "values": ["sales_gwh"], "time": "period"},
}


@dataclass
class Warehouse:
    cfg: Config
    backend: str = WAREHOUSE_BACKEND

    def __post_init__(self) -> None:
        self.cfg.ensure_dirs()

    # --------------------------------------------------------------- duckdb
    @contextmanager
    def _conn(self) -> Iterator["object"]:
        import duckdb  # local import; only when backend == duckdb
        conn = duckdb.connect(str(self.cfg.duckdb_path))
        try:
            yield conn
        finally:
            conn.close()

    def _csv_path(self, table: str) -> Path:
        return self.cfg.warehouse_dir / f"{table}.csv"

    # ---------------------------------------------------------------- upsert
    def upsert(self, table: str, df: pd.DataFrame) -> int:
        """Idempotent upsert keyed on the table's key columns. Returns total rows."""
        if table not in SCHEMAS:
            raise KeyError(f"unknown table {table}")
        keys = SCHEMAS[table]["keys"]
        if df.empty:
            return self.count(table)
        df = df.copy()
        df["fetched_at"] = datetime.now(timezone.utc).isoformat()

        if self.backend == "duckdb":
            with self._conn() as conn:
                cols_sql = ", ".join(f'"{c}"' for c in df.columns)
                conn.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df LIMIT 0")
                # Ensure schema exists even if df was created above with 0 rows.
                conn.register("incoming", df)
                cond = " AND ".join(f"{table}.{k} = incoming.{k}" for k in keys)
                conn.execute(
                    f"DELETE FROM {table} WHERE EXISTS "
                    f"(SELECT 1 FROM incoming WHERE {cond})"
                )
                conn.execute(f"INSERT INTO {table} ({cols_sql}) SELECT {cols_sql} FROM incoming")
                conn.unregister("incoming")
                n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        else:  # csv fallback
            path = self._csv_path(table)
            if path.exists():
                old = pd.read_csv(path)
                combined = pd.concat([old, df], ignore_index=True)
                combined = combined.drop_duplicates(subset=keys, keep="last")
            else:
                combined = df
            combined.to_csv(path, index=False)
            n = len(combined)

        self._update_manifest(table, df)
        log.info("upsert %s: +%d rows -> %d total", table, len(df), n)
        return n

    # ------------------------------------------------------------------ read
    def read(self, table: str, where: str | None = None) -> pd.DataFrame:
        if self.backend == "duckdb":
            if not self.duckdb_has(table):
                return pd.DataFrame()
            with self._conn() as conn:
                q = f"SELECT * FROM {table}"
                if where:
                    q += f" WHERE {where}"
                return conn.execute(q).df()
        path = self._csv_path(table)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def duckdb_has(self, table: str) -> bool:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [table]
            ).fetchall()
            return len(rows) > 0

    def count(self, table: str) -> int:
        if self.backend == "duckdb":
            if not self.duckdb_has(table):
                return 0
            with self._conn() as conn:
                return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        path = self._csv_path(table)
        return len(pd.read_csv(path)) if path.exists() else 0

    def export_parquet(self, table: str) -> Path | None:
        """Materialize a table to Parquet (for portability / CI artifacts)."""
        if self.backend != "duckdb" or not self.duckdb_has(table):
            return None
        out = self.cfg.warehouse_dir / f"{table}.parquet"
        with self._conn() as conn:
            conn.execute(f"COPY {table} TO '{out}' (FORMAT PARQUET)")
        return out

    # -------------------------------------------------------------- manifest
    def load_manifest(self) -> dict:
        if self.cfg.manifest_path.exists():
            return json.loads(self.cfg.manifest_path.read_text())
        return {}

    def _ba_col(self, table: str) -> str | None:
        """The entity column whose per-value watermark we track (BA or state)."""
        keys = SCHEMAS[table]["keys"]
        for c in ("ba", "from_ba", "state"):
            if c in keys:
                return c
        return None

    def _update_manifest(self, table: str, df: pd.DataFrame) -> None:
        man = self.load_manifest()
        tcol = SCHEMAS[table]["time"]
        entry = man.get(table, {})

        # Global watermark (max period seen).
        cur_max = entry.get("watermark")
        new_max = max(list(df[tcol].astype(str)) + ([cur_max] if cur_max else []))
        entry["watermark"] = new_max

        # Per-entity watermark: correct even when only some BAs are pulled.
        bacol = self._ba_col(table)
        if bacol and bacol in df.columns:
            by = entry.get("watermark_by_ba", {})
            grp = df.groupby(bacol)[tcol].max().astype(str)
            for ba, wm in grp.items():
                prev = by.get(str(ba))
                by[str(ba)] = max(wm, prev) if prev else wm
            entry["watermark_by_ba"] = by

        entry["rows_last_upsert"] = int(len(df))
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        man[table] = entry
        self.cfg.manifest_path.write_text(json.dumps(man, indent=2, sort_keys=True))

    def watermark(self, table: str) -> str | None:
        return self.load_manifest().get(table, {}).get("watermark")

    def watermark_by_ba(self, table: str) -> dict[str, str]:
        return self.load_manifest().get(table, {}).get("watermark_by_ba", {})
