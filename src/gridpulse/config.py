"""Central configuration: paths, env, logging, and feature detection.

Everything is env-driven with sane defaults so the pipeline runs from zero.
Optional dependencies (duckdb, matplotlib, ...) are detected here so the rest
of the codebase can degrade gracefully instead of hard-failing on import.
"""
from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # dotenv is a core dep, but keep import defensive
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

_LOG_CONFIGURED = False


def _has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


# Feature flags derived from what is actually installed.
HAS_DUCKDB = _has("duckdb")
HAS_PYARROW = _has("pyarrow")
HAS_MATPLOTLIB = _has("matplotlib")
HAS_SKLEARN = _has("sklearn")
HAS_SCIPY = _has("scipy")
HAS_CVXPY = _has("cvxpy")
HAS_PYMC = _has("pymc")
HAS_STATSMODELS = _has("statsmodels")

# The DuckDB+Parquet warehouse activates only when both are present.
WAREHOUSE_BACKEND = "duckdb" if (HAS_DUCKDB and HAS_PYARROW) else "csv"


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parent.parent.parent


@dataclass
class Config:
    repo_root: Path = field(default_factory=_find_repo_root)
    eia_api_key: str | None = None
    backfill_months: int = 48
    request_timeout: int = 60
    max_retries: int = 5
    page_length: int = 5000
    log_level: str = "INFO"

    # --- derived paths ---
    @property
    def data_dir(self) -> Path:
        d = os.getenv("GRIDPULSE_DATA_DIR")
        return Path(d) if d else self.repo_root / "data"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def warehouse_dir(self) -> Path:
        return self.data_dir / "warehouse"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def figs_dir(self) -> Path:
        return self.data_dir / "figs"

    @property
    def duckdb_path(self) -> Path:
        return self.warehouse_dir / "gridpulse.duckdb"

    @property
    def manifest_path(self) -> Path:
        return self.warehouse_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        for d in (self.cache_dir, self.warehouse_dir, self.raw_dir, self.figs_dir):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def has_key(self) -> bool:
        return bool(self.eia_api_key) and self.eia_api_key not in {"your_key_here", ""}


def load_config() -> Config:
    """Build a Config from environment (loading .env at repo root if present)."""
    root = _find_repo_root()
    load_dotenv(root / ".env")
    cfg = Config(
        repo_root=root,
        eia_api_key=os.getenv("EIA_API_KEY"),
        backfill_months=int(os.getenv("GRIDPULSE_BACKFILL_MONTHS", "48")),
        request_timeout=int(os.getenv("GRIDPULSE_REQUEST_TIMEOUT", "60")),
        max_retries=int(os.getenv("GRIDPULSE_MAX_RETRIES", "5")),
        log_level=os.getenv("GRIDPULSE_LOG_LEVEL", "INFO"),
    )
    return cfg


def setup_logging(level: str = "INFO") -> logging.Logger:
    global _LOG_CONFIGURED
    if not _LOG_CONFIGURED:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        _LOG_CONFIGURED = True
    return logging.getLogger("gridpulse")
