# gridpulse EVIDENCE

## Phase A validation: computed AEF vs EIA published hourly CO2

Window: `2026-04-01T00` → `2026-07-03T17` (UTC). Ground truth: EIA Hourly Electric Grid Monitor per-BA workbooks, `CO2 Emissions Generated` (metric tons/hr) ÷ `Net generation` (MWh).

| BA | EIA AEF | gridpulse AEF (indep) | err | gridpulse AEF (EIA factors) | err |
|---|---:|---:|---:|---:|---:|
| BPAT | 5.3 | 1.7 | -68.3% | 1.5 | -72.31% |
| CISO | 54.2 | 52.0 | -4.1% | 45.2 | -16.52% |
| DUK | 309.0 | 310.4 | +0.5% | 292.3 | -5.38% |
| ERCO | 288.4 | 290.2 | +0.6% | 281.5 | -2.41% |
| MISO | 380.9 | 386.1 | +1.4% | 378.5 | -0.63% |
| NEVP | 252.5 | 277.3 | +9.8% | 249.4 | -1.22% |
| PSCO | 316.9 | 299.6 | -5.5% | 311.9 | -1.59% |
| SOCO | 362.7 | 386.7 | +6.6% | 357.2 | -1.52% |

Median |error| (all 8 BAs) with independent literature factors: **4.8%**; using EIA's own per-fuel factors: **2.00%**.

For fossil-dominated BAs (EIA AEF > 50 kg/MWh, n=7), median |error| with EIA factors is **1.59%** — confirming gridpulse reproduces EIA's published methodology. Larger relative errors are confined to (a) near-zero-carbon BAs like BPAT (~5 kg/MWh, where a tiny absolute gap is a huge percentage) and (b) storage/import-heavy BAs like CISO, where battery discharge counted as gross generation inflates the AEF denominator vs. EIA's net generation.

All AEF values in kg CO2 / MWh.

## Phase B: weather-aware forecasting (ERCO)

Rolling-origin backtest (12 folds, weekly horizon), HistGB quantile model. Weather = Open-Meteo degree-hours (cooling/heating) at the BA load center. Leakage guards (causal features, expanding folds) intact.

- Seasonal-naive MAE: **5516 MWh**
- Model MAE (calendar+lag): **2302 MWh** (skill vs naive 58%)
- Model MAE (+ weather): **1911 MWh** (skill vs naive 65%)
- **Weather feature gain: 17.0% lower MAE**
- 80% conformal-band coverage (weather model): 78%
