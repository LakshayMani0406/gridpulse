# PLAN — build order and status

Delivered in loops (plan → build → run → verify). Full checklist in `CHANGELOG.md`.

## v0.1.0 core (done, 41 tests green)
config · regions · EIA v2 ingest (retry/paginate/cache) · DuckDB+Parquet storage
with per-BA incremental watermark · emissions (AEF + Siler-Evans MEF + bootstrap
CI) · analysis (siting index, inversions) · quantile forecaster + backtest +
conformal · reporting · pipeline · CLI · synthetic fixture.

## Phase A — live + validated on real EIA data
1. Install `.[prod,dev]`, activate DuckDB path, reuse EIA key. ✅
2. Incremental backfill (fuel/demand/interchange/retail) with idempotent upsert
   and watermark. ✅ (verified: re-run delta = 0)
3. Cross-check computed AEF vs EIA's **published** hourly CO2, per BA, with
   tolerance — `validate.py` → `EVIDENCE.md`.
4. Real MEFs + bootstrap CIs per BA; charts from real data (no watermark).
5. CI: monthly cron + `workflow_dispatch` running the live pull with the
   `EIA_API_KEY` secret; manual-dispatch proof.

## Phase B — research edges (≥3)
1. **Consumption-based flow-tracing** (centerpiece) — `flowtrace.py`. ✅ solver verified.
2. **Actual-vs-optimal siting gap** on real FracTracker data — `siting.py`. ✅
3. **Weather-aware forecasting** — `weather.py` + `forecasting.py`. ✅ live fetch verified.
4. **Dashboard** — `dashboard.py` (Streamlit). ✅

## Definition of done
Live incremental pipeline on demand + schedule; AEF validated vs EIA; consumption
flow-tracing used in siting; real siting gap quantified; ≥3 Phase-B edges built,
tested, documented with real numbers in `EVIDENCE.md`/`FINDINGS.md`; full suite
green; README reproduces from zero.
