"""Deterministic synthetic fixture with a *planted* average-vs-marginal inversion.

Used for offline runs (no API key) and tests. Every BA has a known baseload
mix and a known marginal fuel, so we can assert both that the MEF estimator
recovers the planted marginal intensity and that AEF/MEF rank regions
differently. Figures produced from this data are watermarked SYNTHETIC.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .regions import factor_for

# archetype -> (constant baseload by fuel [MWh], marginal fuel, marginal swing [MWh])
_ARCHETYPES = {
    # Hydro-rich: very low AEF, but the extra MWh is gas -> high MEF. (BPAT-like)
    "HYDROX": ({"WAT": 8000.0, "NG": 500.0}, "NG", 3000.0),
    # Gas-heavy: moderate AEF, gas margin -> MEF ~ AEF. (CISO-like)
    "GASX": ({"NG": 6000.0, "SUN": 2000.0}, "NG", 3500.0),
    # Coal-heavy: high AEF, and coal on the margin too -> high MEF. (basin-like)
    "COALX": ({"COL": 7000.0, "NG": 1000.0}, "COL", 2500.0),
    # Nuclear-rich with gas margin: low-ish AEF, gas margin. (SOCO/DUK-like)
    "NUKEX": ({"NUC": 6000.0, "NG": 800.0}, "NG", 2800.0),
}


def make_fixture(hours: int = 24 * 90, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (fuel_long, demand_long) tidy frames for the synthetic BAs."""
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2023-01-01", periods=hours, freq="h")
    # Diurnal + weekly load shape in [0, 1].
    h = np.arange(hours)
    shape = (
        0.5
        + 0.35 * np.sin(2 * np.pi * (h % 24) / 24 - np.pi / 2)
        + 0.1 * np.sin(2 * np.pi * (h % 168) / 168)
    )
    shape = np.clip(shape, 0.05, None)

    fuel_rows, dem_rows = [], []
    for ba, (baseload, marg_fuel, swing) in _ARCHETYPES.items():
        marg = swing * shape + rng.normal(0, swing * 0.02, hours)  # marginal MWh (noisy)
        marg = np.clip(marg, 0, None)
        for t_i, t in enumerate(periods):
            total = 0.0
            for fuel, mw in baseload.items():
                fuel_rows.append({"period": t.isoformat(), "ba": ba, "fueltype": fuel, "mwh": mw})
                total += mw
            # add marginal fuel on top of any baseload of the same fuel
            fuel_rows.append(
                {"period": t.isoformat(), "ba": ba, "fueltype": marg_fuel, "mwh": float(marg[t_i])}
            )
            total += marg[t_i]
            dem_rows.append({"period": t.isoformat(), "ba": ba, "mwh": float(total)})

    fuel_long = pd.DataFrame(fuel_rows)
    demand_long = pd.DataFrame(dem_rows)
    return fuel_long, demand_long


def planted_mef(ba: str) -> float:
    """The true marginal intensity (kg/MWh) planted for a synthetic BA."""
    _, marg_fuel, _ = _ARCHETYPES[ba]
    return factor_for(marg_fuel)
