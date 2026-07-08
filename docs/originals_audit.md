# Originals Audit: what the two prototypes actually are, and what gridpulse got wrong or missed

**Date:** 2026-07-07
**Scope:** read-only audit of the two repos gridpulse was said to "merge" (built on inferred guesses, without ever reading them). Both cloned fresh from GitHub and read directly. Every claim below traces to a file/line I read or a `SELECT`-only query I ran against the committed data. No repo was modified (this report is the only artifact); the originals' code, and gridpulse's code/paper/numbers, are untouched.

- `ai-energy-forecast-tracker` — large (53 py files, ~6.4k LOC, committed 6 MB DuckDB, PyMC fusion, dashboard, API).
- `us-datacenter-emissions-analysis` — small (one Jupyter notebook, one R Markdown, an 11-row 652-byte CSV).

## TL;DR

| | Real thesis | Data | Core result trustworthy? | gridpulse status |
|---|---|---|---|---|
| **us-datacenter-emissions-analysis** | Back-test LBNL's 2024 DC CO₂ forecast vs independent actuals (OLS) | Real-sourced but tiny (11 annual rows), hardcoded | **No** — headline regression is a tautology; "underestimate" is a manufactured carbon-intensity swap | **Not done in gridpulse** (question genuinely missing) |
| **ai-energy-forecast-tracker** | Forecast US AI-DC energy/CO₂ to 2030 + "grade institutions vs measured actuals" | Real EIA/eGRID ingested, but a key series is ~3× inflated; no measured DC series exists | **No** — the scoreboard grades institutions against the model's own posterior (circular) | **Not done in gridpulse** (forecasting/scoreboard absent) |

**Verdict:** gridpulse is not a superset of either original. It kept the *domain* (US datacenter energy/emissions) and the *data-engineering rigor* (real EIA-930, DuckDB, validation), but pivoted to a different question (siting under marginal-carbon-accounting ambiguity) and dropped both originals' actual theses. What is worth reclaiming is the **LBNL forecast back-test question** — done properly, not the way the original did it.

---

## 1. us-datacenter-emissions-analysis

### What it actually is
Thesis (README:9): *"Are LBNL's 2024 congressionally-mandated predictions about U.S. data center CO₂ emissions accurate when verified against independent 2025/2026 data?"* Three phases: Python EDA + prediction-gap (notebook), R OLS regression of the drivers (`phase2_regression.rmd`), Python 2030 scenario forecast (notebook). This is exactly the LBNL-forecast-back-test question and it is a legitimate, on-topic question.

### Data — real source, toy size, hardcoded
Real-sourced (LBNL 2024 energy, Ember 2026 grid carbon intensity, EIA renewables, Guidi et al. 2024 and IEA 2025 as independent actuals) but **11 annual rows (2014–2024)**, hardcoded identically in `master_dataset.csv` and notebook cell 1. Only **two** genuinely independent measured-emissions points exist: Guidi 2018 = 31.5 Mt, IEA 2024 = 105 Mt (`Actual_CO2_MtCO2`). Everything else labeled "actual" is derived.

### Correctness — the headline results do not hold

1. **The regression is a tautology (fatal to the headline).** `Derived_CO2_MtCO2` equals `DC_Energy_TWh × Grid_CarbonIntensity_gCO2perKWh ÷ 1000` **exactly** — I checked all 11 rows, max residual 0.004 Mt (pure 2-dp rounding). The R model (`phase2_regression.rmd:52-56`) then regresses `Derived_CO2 ~ Energy + CarbonIntensity + Renewables`, i.e. it fits a product identity with a linear-in-its-own-factors model. So "DC energy explains 99.6% of variance (R²=0.9959)" and "every 1 TWh adds 0.33 Mt" are **construction artifacts**, not empirical findings. (The slope 0.3328 is below the mean grid CI of 0.446 t/MWh only because CI falls as energy rises over the window — a linearization of the identity, nothing more.)

2. **The "31.3% underestimate" is manufactured.** `Derived_CO2` = LBNL's own energy × Ember's CI (383–529 g/kWh); `LBNL_Predicted_CO2` = LBNL's energy × a flat 340 g/kWh (README:16). The entire "gap" is the carbon-intensity assumption swap applied to the same energy — a sensitivity to one input, presented as a verified prediction error against measured reality.

3. **Internally inconsistent about what "actual" is.** For 2024 there are three numbers: LBNL 62.2, their "derived actual" 70.2, and the independent IEA actual 105. Their own derived series is **33% below** the real actual (LBNL is 41% below). The notebook's "gap is shrinking to 12.9% by 2024" (cell 11) uses derived-vs-LBNL, which shrinks only because Ember's CI approaches LBNL's 340 as the grid decarbonizes — while against the true 105 actual, LBNL is *more* wrong, not less.

4. **Tiny-n, trending time series.** n=11, three collinear monotone-trending predictors; the `.rmd` itself flags high VIF (`:63-70`) and retreats to single-predictor models, but never addresses non-stationarity / residual autocorrelation → spurious-regression risk.

5. **The 2030 forecast contradicts its own story.** Phase 3 (notebook cell 10) applies energy-only `CO2 = 10.207 + 0.333·Energy` to hardcoded energy scenarios (200–490 TWh), implicitly freezing carbon intensity at the fitted blend — directly contradicting the decarbonization trend the analysis highlights. It overstates 2030 CO₂.

### Quality read
Clean narrative, honest in places (Guidi "not a complete national census"), real sourcing — but the central statistical claims are circular/manufactured and internally inconsistent. Coursework-grade. The *direction* (LBNL's flat 340 g/kWh CI is probably too low for DC-heavy grids) is plausible; the *quantification* is not rigorous.

---

## 2. ai-energy-forecast-tracker

### What it actually is
Thesis: forecast US AI-datacenter energy/CO₂ to 2030 with four time-series models, and run *"a living scoreboard that grades every major published institutional forecast against measured actuals"* (README:5). The load-bearing word is **"measured"** — and there is no measured US-datacenter-energy series anywhere in the repo; every "actual" is the fusion model's posterior mean. The methodology is quieter and more honest than the README: it grades forecasts against "the *resulting* actuals" (methodology.md:12) and states outright that "the posterior mean is used as the 'actual'" (methodology.md:220; `forecasts.py:190-221`).

### Data — real ingestion, one series badly wrong, results shipped as a binary
- Real EIA API data (`eia_commercial_monthly`, 302 mo, 2001–2026) and real EPA eGRID (`egrid_state_yearly`, 208 rows, 2020–23; `epa_egrid.py` parsing is genuine and correct).
- **`warehouse.duckdb` (6 MB) is committed to git** (`git ls-files` shows it) despite README:102 claiming it is gitignored/regenerated. The shipped results are a frozen binary.
- FERC table does not exist (empty stub; `ferc_interconnection.py` is scaffolding).

### Correctness — top 5 (all verified directly)

1. **The core "scoreboard vs measured actuals" is circular (fatal to the thesis).** The three institutional numbers are hardcoded anchors (`bayesian_model.py:63-67`: `183.0 / 105.0 / 31.5`) that the fusion model is *fit to* as likelihoods (`:224-236`, `pm.Normal(observed=BENCHMARKS[...])`). The scoreboard then grades those same institutions against `fusion_posterior` — the model's own output (`forecasts.py:190-221`). Worse, the model **misses its own anchors** (I summed the posterior): 2018 CO₂ 31.5 → **60.0** (+90%), 2024 CO₂ 105 → **67.7** (−36%), 2024 IT energy 183 → **140** (187.6 total ÷ 1.34, −23%). So the headline "IEA's 105 Mt vs our 68, grade F" (README:18,52) is the model failing to fit its own input, relabeled as IEA being wrong. There is no independent measured actual anywhere to grade against.

2. **EIA commercial series ~3× inflated.** `commercial_gwh` averages 330,497 GWh/mo = **3,966 TWh/yr**, vs the true US commercial sector ~1,350 TWh/yr (the repo's own seed value, `eia.py:93`). Cause: `eia.py:75` does `groupby("ds").sum()` with no `stateid` filter, summing state rows + the `US` total + census-region/division aggregates. This breaks any "datacenters as a share of commercial load" interpretation and the state-decomposition weights.

3. **Not reproducible as shipped.** `retrain.yml:22` installs `requirements.txt` = {streamlit, pandas, numpy, plotly, duckdb, scikit-learn, pyarrow} — missing `requests`, `python-dotenv`, `prophet`, `mlflow`, `pymc`; the first real step (`:27` `python src/ingest/eia.py`) imports `requests`/`dotenv` → `ModuleNotFoundError`. The workflow also runs legacy `train.py` (`:30`), not the fusion→4-model→benchmark sequence, so it never rebuilds `fusion_posterior`/`benchmark_scores`. Only the manual README sequence works (needs PyMC ~10 min + an EIA key).

4. **Degenerate OLS "forecast model."** `ols_model.py:47` keeps full years only (`HAVING COUNT(*)=24`), then holdout 1 year → tests on a **single point (2025)**; and its predictors (`dc_twh`, `co2_rate`) and target (`co2_mt`) are algebraically linked (`co2 ≈ energy × rate`), so it refits an identity. The reported R²≈0.97 is trivial.

5. **Duplication and dead computation.** Two packages both named `simulation_engine` (root `simulation_engine/` and `src/simulation_engine/`, both present) resolved by `sys.path` insertion order — fragile. `seed.py:18-27` hardcodes an `ACTUALS` dict labeled "from fusion_posterior" but static and partly inconsistent with it: 2024 (187.6/67.7) matches the posterior, but 2020 energy is 73.4 vs the posterior's 146.3 (~2× off), and 73.4 ≈ LBNL's 73 TWh *forecast* for 2020 — a forecast mislabeled as an actual. Fusion computes a DC-weighted CO₂ rate it never uses (`bayesian_model.py`), with a comment (`:42`) contradicting the methodology on whether VA is cleaner or dirtier.

### Engineering / quality
2 test files / 15 tests for 53 files; they assert DataFrame shapes and the *narrative* ("LBNL underestimated") against the committed DuckDB, so they pass even if every pipeline script were deleted. Zero coverage of the fusion math, ingestion, the four forecast bodies, MC, agents, or API. Genuinely more ambitious than the other repo (real ingestion, PyMC hierarchical fusion, Streamlit + FastAPI) but the flagship result is circular, a key input is 3× wrong, and it does not reproduce as shipped.

---

## 3. gridpulse vs the real originals

### What gridpulse faithfully captured
- The **domain** (US datacenter energy/emissions; LBNL/IEA framing) and the **data-engineering discipline**: real EIA-930 ingestion, a DuckDB warehouse, and a validation habit.
- gridpulse's AEF validated against EIA's *published* hourly CO₂ (median 1.59%) is the kind of rigorous, independent validation **both originals lacked** — it did not inherit their circular/tautological validation shortcuts.

### What gridpulse got wrong or missed
- **Missed us-datacenter-emissions-analysis's entire thesis.** gridpulse contains no LBNL-forecast-vs-actual back-test (verified: no LBNL/IEA back-test, no benchmark scoring in `src/` or `PAPER.md`). It used LBNL/FracTracker figures only as *siting-scenario inputs* and validated its own factors against EIA-930 — a different question. (This is the gap you already flagged; confirmed.)
- **Missed ai-energy-forecast-tracker's thesis too.** gridpulse does not forecast national DC energy/CO₂ to 2030 and has no institutional-forecast scoreboard. Its only forecasting is short-term weather-aware **balancing-authority demand** (`model.py`, `forecasting.py`), which is unrelated.
- **So the "merge" was actually a pivot.** gridpulse is a different, stronger project (siting under accounting-method ambiguity, the min-max-regret result) in the same domain. It neither reproduces nor supersedes the two originals' core deliverables; it set them aside.
- **One inherited assumption to flag:** gridpulse treats LBNL inputs as reliable scenario baselines. The (flawed but directionally real) point of the us-repo is that LBNL's carbon-intensity assumption is contestable — something gridpulse could acknowledge as an input sensitivity.

---

## 4. Merge / rebuild recommendation

### Does gridpulse subsume each original?
- **us-datacenter-emissions-analysis:** No. The LBNL back-test question is genuinely absent from gridpulse.
- **ai-energy-forecast-tracker:** No. National forecasting + institutional scoreboard are absent. gridpulse's EIA data engineering is already better than this repo's (which has the 3× bug), so nothing there is worth importing wholesale.

### What is worth folding INTO gridpulse
1. **The LBNL forecast back-test, done properly (recommended, high value).** This is the one genuinely missing, on-thesis result and it strengthens gridpulse's "the accounting choice matters" argument with a forecast-accuracy angle. Do it rigorously, i.e. the opposite of the original:
   - Compare LBNL 2024's *published* DC energy and CO₂ trajectory to **genuinely independent measured actuals** (IEA 2025: 105 Mt / ~183 TWh IT; Guidi 2018: 31.5 Mt; EIA-derivable where possible).
   - **Decompose** LBNL's CO₂ error into (i) energy-projection error and (ii) carbon-intensity-assumption error (LBNL's flat ~340 g/kWh vs realized grid CI at DC-weighted locations). This is the real, defensible finding.
   - **Do not** regress a derived `E×CI` identity; report the decomposition directly. **Reconcile** the 70-vs-105 scope discrepancy honestly (facility boundary / census vs sample).
2. **An institutional-forecast scoreboard (optional, second priority)** — only if graded against independent measured actuals, never against model output.

### Reusable code (specific)
- `ai-energy-forecast-tracker/src/benchmarks/forecasts.py`: the grading skeleton (`assign_grade`/`assign_bias`/error%, `:226-252`) and the curated `PUBLISHED_FORECASTS` catalog with real citations/URLs (`:38-185`) are usable **scaffolding** for the scoreboard — but `load_actuals` (`:190-221`) must be thrown out and replaced with real actuals (it is the exact circular bug to avoid).
- `us-datacenter-emissions-analysis/master_dataset.csv`: the curated LBNL/Ember/Guidi/IEA table is a useful **data starting point** for the back-test — but the `Derived_CO2` column must be dropped (it is the tautology) and replaced with the independent measured actuals.
- `ai-energy-forecast-tracker/src/ingest/epa_egrid.py`: a correct eGRID parser, but it yields state **average** EF, which is off-thesis for gridpulse's **marginal per-BA** focus — low value.
- **Everything else is superseded or wrong** and should be archived: the us-repo regression/forecast (circular), the ai-repo fusion model (doesn't fit its anchors, off-thesis), the 3×-inflated EIA ingestion, both `simulation_engine` trees, the display-only agents, the degenerate OLS, and both repos' test suites.

### Proposed concrete next step (for your approval — not implemented)
Add a small, self-contained **"LBNL 2024 forecast back-test"** to gridpulse: one new module (e.g. `src/gridpulse/lbnl_backtest.py`) + tests + a short FINDINGS/PAPER subsection, that pulls LBNL's published trajectory, compares it to independent measured actuals, and decomposes the error into energy vs carbon-intensity components — reusing the `forecasts.py` grading skeleton and the curated data table, but with real actuals and no tautological regression. Estimated ~1 focused session. **Approve / decline / modify** and I'll proceed (or not).

*Non-goals honored: no gridpulse code/number/paper changes; no new repo; no re-merge; the originals were not archived and their READMEs not edited beyond the superseded banners already committed in the prior step.*
