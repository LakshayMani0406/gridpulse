"""Balancing authorities, fuel taxonomy, and CO2 emission factors.

Sources
-------
- Balancing-authority codes/names: EIA-930 (Hourly Electric Grid Monitor).
- Emission factors (kg CO2 / MWh generated), by EIA fuel code: the de Chalendar
  et al. 2019 (PNAS) / `jdechalendar/gridemissions` default table. Natural gas is
  reported by the EIA API under the code ``NG`` (gridemissions calls it ``GAS``).
  These are generation-based factors; they are used both to compute AEF and are
  validated against EIA's own published hourly CO2 in Phase A.
"""
from __future__ import annotations

from dataclasses import dataclass

# Canonical basis: EIA's *production* CO2 counts only fossil-fuel combustion;
# nuclear/hydro/solar/wind contribute zero. Using this basis makes gridpulse's
# AEF directly comparable to EIA's published hourly CO2 (Phase A validation),
# and leaves the Siler-Evans MEF unchanged (the margin is fossil regardless).
# Fossil factors are the de Chalendar 2019 / gridemissions defaults (kg/MWh);
# Phase A additionally extracts EIA's own per-fuel factors from the workbooks
# for a near-exact match and reports agreement under these independent factors.
# EIA's Hourly Grid Monitor publishes CO2 *factor* columns for only COL, NG, and
# OIL -- it applies no fossil factor to "Other" (OTH), which is dominated by
# storage (battery charge/discharge nets ~0) and non-combustion sources.
# Matching that: OTH -> 0. Empirically this reproduces EIA's per-BA CO2 far
# better, especially for storage-heavy BAs like CISO (see EVIDENCE.md).
EMISSION_FACTORS_KG_PER_MWH: dict[str, float] = {
    "COL": 1000.0,  # coal
    "NG": 469.0,    # natural gas (gridemissions "GAS")
    "OIL": 840.0,   # petroleum
    "OTH": 0.0,     # other -- EIA applies no factor (storage/non-combustion)
    "NUC": 0.0,     # nuclear      -- zero on EIA production basis
    "WAT": 0.0,     # hydro
    "SUN": 0.0,     # solar
    "WND": 0.0,     # wind
    "GEO": 0.0,     # geothermal
    "BIO": 0.0,     # biomass (biogenic; excluded from EIA fossil CO2)
    "UNK": 0.0,     # unknown
}

# Lifecycle / embodied-carbon factors (kg CO2e/MWh), for documented sensitivity
# analysis only. Ref: gridemissions EMISSIONS_FACTORS (Schivley 2018 for UNK).
LIFECYCLE_FACTORS_KG_PER_MWH: dict[str, float] = {
    "COL": 1000.0, "NG": 469.0, "OIL": 840.0, "OTH": 439.0,
    "NUC": 16.0, "WAT": 4.0, "SUN": 46.0, "WND": 12.0,
    "GEO": 42.0, "BIO": 230.0, "UNK": 439.0,
}

# Fuels whose output carries direct combustion CO2 and that typically set the
# margin (dispatchable fossil). Used by the Siler-Evans marginal estimator.
# Matches EIA's factored fuels (COL, NG, OIL); "Other" is excluded (storage /
# non-combustion, no EIA factor).
FOSSIL_FUELS: frozenset[str] = frozenset({"COL", "NG", "OIL"})

# Zero-marginal-cost / non-dispatchable-at-margin (informational).
CLEAN_FUELS: frozenset[str] = frozenset({"NUC", "WAT", "SUN", "WND", "GEO"})


def factor_for(fuel: str) -> float:
    """CO2 factor (kg/MWh) for an EIA fuel code, defaulting unknown fuels to OTH."""
    return EMISSION_FACTORS_KG_PER_MWH.get(fuel.upper(), EMISSION_FACTORS_KG_PER_MWH["OTH"])


@dataclass(frozen=True)
class Region:
    code: str          # EIA BA code (respondent)
    name: str
    nerc: str          # NERC region
    interconnect: str  # Eastern | Western | Texas
    lat: float = 0.0   # representative load-center latitude
    lon: float = 0.0   # representative load-center longitude


# A geographically and fuel-diverse set of major US balancing authorities that
# report hourly fuel-type data in EIA-930. Covers all three interconnects and
# spans hydro-heavy (BPAT), gas-heavy (ERCO/CISO), coal-heavy (basin BAs), and
# nuclear-heavy (SOCO/DUK) systems -- exactly the average-vs-marginal contrast.
REGIONS: dict[str, Region] = {
    r.code: r
    for r in [
        # --- Large ISOs / RTOs ---
        Region("CISO", "California ISO", "WECC", "Western", 36.7, -119.7),
        Region("ERCO", "Electric Reliability Council of Texas", "TRE", "Texas", 31.0, -99.0),
        Region("PJM", "PJM Interconnection", "RFC", "Eastern", 40.0, -78.0),
        Region("MISO", "Midcontinent ISO", "MRO", "Eastern", 42.0, -91.0),
        Region("SWPP", "Southwest Power Pool", "MRO", "Eastern", 37.5, -97.5),
        Region("ISNE", "ISO New England", "NPCC", "Eastern", 42.5, -71.5),
        Region("NYIS", "New York ISO", "NPCC", "Eastern", 42.9, -75.5),
        # --- Western utility BAs (hydro / solar / coal contrast) ---
        Region("BPAT", "Bonneville Power Administration", "WECC", "Western", 45.5, -121.5),
        Region("PACW", "PacifiCorp West", "WECC", "Western", 44.0, -121.0),
        Region("PACE", "PacifiCorp East", "WECC", "Western", 41.0, -111.9),
        Region("PSCO", "Public Service Company of Colorado", "WECC", "Western", 39.7, -104.99),
        Region("PNM", "Public Service Company of New Mexico", "WECC", "Western", 35.1, -106.6),
        Region("AZPS", "Arizona Public Service", "WECC", "Western", 33.4, -112.0),
        Region("SRP", "Salt River Project", "WECC", "Western", 33.4, -111.9),
        Region("NEVP", "Nevada Power Company", "WECC", "Western", 36.1, -115.1),
        Region("PGE", "Portland General Electric", "WECC", "Western", 45.5, -122.6),
        Region("IPCO", "Idaho Power Company", "WECC", "Western", 43.6, -116.2),
        Region("WACM", "Western Area Power - Rocky Mountain", "WECC", "Western", 40.0, -105.0),
        Region("LDWP", "Los Angeles Dept of Water and Power", "WECC", "Western", 34.05, -118.24),
        # --- Eastern / Southeast utility BAs (nuclear / gas / coal) ---
        Region("SOCO", "Southern Company Services", "SERC", "Eastern", 33.7, -84.4),
        Region("TVA", "Tennessee Valley Authority", "SERC", "Eastern", 35.5, -86.6),
        Region("DUK", "Duke Energy Carolinas", "SERC", "Eastern", 35.2, -80.8),
        Region("CPLE", "Duke Energy Progress East", "SERC", "Eastern", 35.8, -78.6),
        Region("FPL", "Florida Power & Light", "FRCC", "Eastern", 26.1, -80.1),
        Region("FPC", "Duke Energy Florida", "FRCC", "Eastern", 28.0, -82.0),
        Region("LGEE", "Louisville Gas & Electric / KU", "SERC", "Eastern", 38.2, -85.7),
        Region("AECI", "Associated Electric Cooperative", "SERC", "Eastern", 38.6, -92.6),
    ]
}

REGION_CODES: list[str] = list(REGIONS.keys())


def all_regions() -> list[Region]:
    return list(REGIONS.values())
