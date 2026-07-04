# Changelog / running checklist

## Phase 3 — research-grade: robustness of siting to accounting choices

- [x] **Thrust 3 — MEF validation** (`causal_mef.py`): triangulate Siler-Evans vs VRE-ramp instrument vs generation-trip instrument. Converge <20% for fossil-margin BAs (PJM 3%, SWPP 6%, SOCO 10%, MISO 15%); diverge for storage/solar-heavy (CISO, ERCO) — the margin is only well-identified where a single fossil unit sets it.
- [x] **Thrust 2 — nodal LME** (`nodal.py`): CAISO OASIS nodal congestion (no-auth, reproducible) → intra-CISO marginal-carbon spread ≈ ±50% around BA-average; cleanest nodes are export-constrained solar buses. (Switched from ERCOT: ERCOT nodal now auth-gated + CEII-restricted.)
- [x] **Thrust 5 — probabilistic siting** (`thrust5.py`): propagate MEF bootstrap CIs → rank distributions, P(in top-k), pairwise P(A greener than B), statistical-tie detection.
- [x] **Thrust 6 — multiverse capstone** (`multiverse.py`, `phase3.py`): specification curve over {temporal × accounting × spatial × method}. 22/27 BAs flip siting rank across just 4 specs; only Pacific-NW hydro robustly green. Spec-curve figure.
- [x] **Thrust 1 — short-run vs long-run** (`thrust1.py`, `cambium.py`): NREL Cambium 2024 LRMER/SRMER fetched per BA (Scenario Viewer API). Short-run→long-run rank flips: **IPCO −22** (hydro greenest short-run, dirty long-run), MISO +16, ISNE +12. Holland reproduction on 2019–2025 backfill: **4 of 8 BAs have a stickier marginal than average**.
- [x] Backward backfill to 2019 (8 fuel-diverse BAs, ~6.3M fuel rows total) for the Holland trend.
- [x] `PAPER.md` (arXiv target) with real §4 results + honest limitations.
- [x] `phase3` master run: 6 specifications, **24/27 BAs flip**, only BPAT+PACW robust-green; spec-curve figure + all FINDINGS sections generated from real data.
- [x] Warehouse hygiene: stopped committing binary warehouse to git; `rebuild_manifest` recovers watermarks from data.
- [x] 63 tests green; ruff clean.

## v0.1.0 — core (built + validated on synthetic, then wired to live data)

- [x] Repo scaffold: `pyproject.toml` (`prod`/`research`/`dev` extras), package layout, `.gitignore`, `.env` (reused EIA key), git init.
- [x] `config.py` — env-driven config, optional-dep feature flags, DuckDB-vs-CSV backend selection, logging.
- [x] `regions.py` — 27 real EIA balancing authorities (3 interconnects), fuel→CO2 factor table (EIA production basis; lifecycle set for sensitivity), load-center coordinates.
- [x] `ingest.py` — EIA v2 client: retry+backoff, offset pagination, on-disk page cache, typed pulls (fuel-type, demand, interchange, retail-sales). **Verified live.**
- [x] `storage.py` — DuckDB(+Parquet) warehouse with CSV fallback; idempotent upsert; **per-BA watermark** manifest for true incremental refresh.
- [x] `emissions.py` — hourly CO2, AEF, Siler-Evans MEF with bootstrap CI. **MEF recovers planted ground truth to 0.0e0 (machine precision), r²=1.0.**
- [x] `analysis.py` — carbon-aware siting index, rank-inversion detection, siting gap.
- [x] `model.py` — leakage-safe features, gradient-boosted quantile forecaster, seasonal-naive baseline, rolling-origin backtest, CQR conformal calibration.
- [x] `reporting.py` — AEF-vs-MEF + rank-scatter + validation charts (SYNTHETIC watermark toggle), markdown report.
- [x] `pipeline.py` — offline (synthetic) + live incremental pull orchestration.
- [x] `cli.py` — `run-offline`, `run-now`, `backfill`, `status`, `validate`.
- [x] `synthetic.py` — deterministic fixture with a planted average-vs-marginal inversion.
- [x] Tests: 41 passing under real `pytest`.

## Phase A — live + validated on real EIA data

- [x] Installed `.[prod,dev]` (duckdb, pyarrow, sklearn, scipy, matplotlib, openpyxl); DuckDB+Parquet path active.
- [x] Live incremental pull verified (idempotent re-run delta = 0; watermark advances).
- [x] Backfill for all 27 BAs: fuel mix + demand (24 months, ~1.5M + ~0.45M rows) + interchange (6 months) + monthly retail sales.
- [x] `validate.py` — cross-check computed AEF vs EIA's **published** hourly CO2 (Grid Monitor per-BA workbooks); reports agreement under independent factors and under EIA's own factors.
- [x] Real MEFs + bootstrap CIs per BA; real charts regenerated (no watermark).
- [x] Validation result: fossil-dominated BAs match EIA's published CO2 to **median 1.6%** using EIA's own factors (ERCO -2.4%, MISO -0.6%, DUK -5.4%, SOCO -1.5%, PSCO -1.6%, NEVP -1.2%). Fixed a real bug: battery/"Other" phantom CO2 (EIA factors only COL/NG/OIL) had thrown CISO off by +67%.
- [ ] CI: manual `workflow_dispatch` proof (needs GitHub push).

## Phase B — research edges

- [x] **Flow-tracing (centerpiece):** `flowtrace.py` — consumption-based (import-adjusted) emissions via the de Chalendar 2019 linear system. **Solver verified against hand-computed 2-node network.** Consumption-based MEF for siting-correct ranking.
- [x] **Real siting gap:** `siting.py` — map facilities→BA (lat/lon or state), combined AEF/prod-MEF/cons-MEF ranking, actual-vs-optimal MtCO2/yr gap. (Awaiting real DC location dataset.)
- [x] **Weather-aware forecasting:** `weather.py` — Open-Meteo ERA5 degree-hours per BA; backtest accepts weather features for a skill comparison. **Live fetch verified.**
- [x] **Dashboard:** `dashboard.py` — Streamlit map + siting explorer + average-vs-marginal scatter.
- [x] FINDINGS.md with real numbers: average→marginal re-ranks sharply (PACE +16, AZPS +15, WACM +14); consumption flow-tracing moves them further; **actual-vs-optimal siting gap = 25.2 MtCO2/yr** (production-marginal, capacity-constrained, 76% of actual).
- [x] Weather-aware forecasting result: **+18.8% lower MAE** (ERCO) from degree-hour features; conformal (CQR) 80% bands calibrated in the backtest. Fixed a real bug: the initial -31% was small-sample eval noise (96 test hours); robust backtest (12 folds x weekly) + HistGBM reveals the true gain.
