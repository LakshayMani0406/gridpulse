# RESEARCH — methods, data, citations

## Data sources (all real, verified 2026-07)

| Source | Route / URL | Used for |
|---|---|---|
| EIA API v2 | `electricity/rto/fuel-type-data` | hourly generation by fuel by BA |
| EIA API v2 | `electricity/rto/region-data` (type=D) | hourly demand by BA |
| EIA API v2 | `electricity/rto/interchange-data` | hourly BA-to-BA flows (flow-tracing) |
| EIA API v2 | `electricity/retail-sales` | monthly retail sales by state |
| EIA Grid Monitor | `gridmonitor/knownissues/xls/{BA}.xlsx`, sheet *Published Hourly Data* | **published hourly CO2** (validation ground truth), incl. `CO2 Emissions Generated/Consumed` |
| FracTracker | National Data Centers Tracker (Google-Sheet CSV) | real data-center MW + lat/lon |
| Open-Meteo | ERA5 archive `temperature_2m` | degree-hour weather features |

EIA publishes hourly CO2 back to 2018-07 and counts CO2 only from fossil
combustion (COL, NG, OIL, "Other"); gridpulse uses the same production basis so
its AEF is directly comparable.

## Methods

- **AEF** — Σ CO2 ÷ Σ generation over the window, per BA. Fossil emission factors
  (kg/MWh): COL 1000, NG 469, OIL 840, OTH 439 (de Chalendar 2019 / gridemissions
  defaults; clean fuels = 0 on EIA production basis). Phase A also extracts EIA's
  own per-fuel factors from the workbooks for a near-exact match.
- **MEF (Siler-Evans, Azevedo & Morgan 2012, *ES&T*, doi:10.1021/es300145v)** —
  OLS of the hour-to-hour ΔCO2 on Δdemand over consecutive hours; bootstrap CI.
  Recovers a planted marginal intensity to machine precision on synthetic data.
- **Consumption-based emissions (de Chalendar, Taggart & Azevedo 2019, *PNAS*,
  doi:10.1073/pnas.1912950116)** — per-hour linear system routing production
  emissions along the interchange network; solver adapted from
  `jdechalendar/gridemissions`. Consumption-based MEF regresses Δ(consumption CO2)
  on Δdemand.
- **Forecasting** — leakage-safe calendar+lag features, gradient-boosted quantile
  regression, seasonal-naive baseline, rolling-origin backtest, CQR conformal
  bands (Romano et al. 2019). Weather variant adds Open-Meteo degree-hours.

## Known approximations (stated honestly)

- Flow-tracing runs on the 27-BA modeled subnetwork, not the full ~66-BA US grid;
  imports from unmodeled BAs are dropped. Validated against EIA's published
  consumption CO2 where available.
- Facility→BA mapping uses nearest modeled load-center (or state) — coarse vs. a
  true BA-boundary point-in-polygon join.
- FracTracker MW is populated on ~500 of 1,593 facilities; the gap uses those.
