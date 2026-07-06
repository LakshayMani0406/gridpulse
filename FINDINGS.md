# gridpulse FINDINGS (real EIA data)

## 1. Average vs. marginal vs. consumption-based re-ranks siting

Three bases per balancing authority: **AEF** (average), **production MEF** (Siler-Evans on own generation), and **consumption MEF** (import-adjusted, via interchange flow-tracing -- the frontier siting number).

Flow-tracing ran over 4288 hours across 27 modeled BAs (subnetwork of the ~66-BA US grid). Consumption MEF is floored at 0 (a constant load's marginal carbon is non-negative; raw estimates dip negative in solar-saturated BAs under the subnetwork approximation).

| BA | AEF | prod MEF | cons MEF | rank(AEF) | rank(prodMEF) | rank(consMEF) | AEF→consMEF |
|---|---:|---:|---:|---:|---:|---:|---:|
| CISO | 173 | 142 | 0 | 4 | 10 | 1 | +3 |
| BPAT | 25 | 7 | 2 | 1 | 1 | 2 | -1 |
| PACW | 106 | 10 | 57 | 2 | 2 | 3 | -1 |
| PGE | 338 | 51 | 80 | 15 | 4 | 4 | +11 |
| PACE | 511 | 122 | 101 | 24 | 8 | 5 | +19 |
| IPCO | 115 | 22 | 126 | 3 | 3 | 6 | -3 |
| LDWP | 345 | 74 | 146 | 16 | 5 | 7 | +9 |
| PSCO | 345 | 98 | 158 | 17 | 7 | 8 | +9 |
| SRP | 217 | 173 | 163 | 6 | 12 | 9 | -3 |
| ERCO | 318 | 257 | 201 | 11 | 15 | 10 | +1 |
| NEVP | 328 | 132 | 203 | 14 | 9 | 11 | +3 |
| PNM | 182 | 263 | 244 | 5 | 16 | 12 | -7 |
| FPL | 321 | 294 | 255 | 12 | 17 | 13 | -1 |
| AZPS | 437 | 94 | 273 | 21 | 6 | 14 | +7 |
| TVA | 324 | 220 | 312 | 13 | 13 | 15 | -2 |
| NYIS | 252 | 255 | 325 | 8 | 14 | 16 | -8 |
| WACM | 617 | 166 | 339 | 25 | 11 | 17 | +8 |
| DUK | 297 | 353 | 350 | 10 | 20 | 18 | -8 |
| ISNE | 279 | 331 | 357 | 9 | 19 | 19 | -10 |
| PJM | 362 | 400 | 444 | 18 | 21 | 20 | -2 |
| CPLE | 222 | 312 | 456 | 7 | 18 | 21 | -14 |
| SOCO | 402 | 436 | 463 | 20 | 23 | 22 | -2 |
| SWPP | 394 | 600 | 515 | 19 | 26 | 23 | -4 |
| FPC | 464 | 426 | 519 | 23 | 22 | 24 | -1 |
| MISO | 446 | 579 | 538 | 22 | 25 | 25 | -3 |
| AECI | 697 | 527 | 706 | 26 | 24 | 26 | +0 |
| LGEE | 874 | 695 | 791 | 27 | 27 | 27 | +0 |

Average vs. production-marginal already re-ranks sharply: **PACE** (+16), **AZPS** (+15), **WACM** (+14) (rank moves, average→marginal). Adding import-adjustment (consumption MEF) moves them further: **PACE** (+19), **CPLE** (-14), **PGE** (+11), **ISNE** (-10).

Positive rerank = a BA that looks dirtier on average is cleaner on the margin (its extra MWh displaces coal with gas/renewables); negative = looks clean on average but its marginal/imported MWh is dirty.

## 2. Actual vs. carbon-optimal data-center build-out

FracTracker's tracked build-out (Operating + approved/under-construction, with capacity) is allocated to modeled BAs by observed share; we then site 10000 MW of new load and price it on the **production marginal** factor (robust, validated). Capacity-constrained optimal = greedy cleanest-first, each BA capped at 20% of its own mean demand (deliverability).

- **Actual** allocation: **33.19 MtCO2/yr**
- **Carbon-optimal, capacity-constrained**: **7.99 MtCO2/yr** → **gap 25.2 MtCO2/yr (76% of actual)**
- Carbon-optimal, unconstrained (all load in cleanest BA, **BPAT** @ 7 kg/MWh): 0.65 MtCO2/yr → gap 32.5 MtCO2/yr (theoretical floor; ignores deliverability)
- Consumption-marginal basis (frontier): constrained gap 31.7 MtCO2/yr

Headline: even respecting a 20%-of-local-demand cap per BA, aligning the build-out to marginal carbon avoids ~**25 MtCO2/yr** on the production-marginal basis.

_Data: FracTracker Alliance National Data Centers Tracker (non-commercial use, credited). Flow-tracing: de Chalendar et al. 2019. Subnetwork of 27 modeled BAs; facility→BA by nearest load center._

## Thrust 3: MEF validated by independent supply-side instruments

The MEF has no published ground truth. We identify it three ways: **Siler-Evans** (ΔCO2 on Δdemand), a **VRE-ramp instrument** (carbon displaced per MWh of exogenous wind/solar; Ricks et al.), and **generation-trip** events (forced outages).

| BA | Siler-Evans | VRE-ramp | outage | spread % |
|---|---:|---:|---:|---:|
| FPC | 426 | 425 | — | 0% |
| PJM | 400 | 414 | — | 3% |
| SWPP | 599 | 567 | — | 5% |
| SOCO | 435 | 480 | — | 10% |
| MISO | 579 | 496 | — | 15% |
| AZPS | 94 | 115 | — | 20% |
| FPL | 294 | 440 | — | 40% |
| ERCO | 256 | 385 | 237 | 51% |
| DUK | 352 | 632 | — | 57% |
| CPLE | 311 | 145 | — | 73% |
| TVA | 219 | 503 | — | 79% |
| SRP | 173 | 428 | 206 | 95% |
| AECI | 526 | 138 | — | 117% |
| CISO | 142 | 25 | — | 141% |
| IPCO | 22 | 42 | 5 | 161% |
| PSCO | 98 | 398 | 22 | 218% |
| PNM | 263 | 70 | -5 | 245% |
| PACE | 121 | 542 | -63 | 303% |
| LDWP | 71 | 299 | -66 | 360% |
| BPAT | 7 | -2 | — | 368% |
| PACW | 10 | 29 | -12 | 463% |
| WACM | 164 | 665 | -316 | 573% |
| NEVP | 132 | 241 | -213 | 847% |

**6 of 23 BAs converge within 20%** across independent methods — real validation where a single fossil unit sets the margin. Estimates **diverge** in solar/storage/import-heavy BAs (batteries and imports break the one-margin assumption). Ref: Environ. Res.: Energy 2024, doi:10.1088/2753-3751/ad72f6.

## Thrust 5: probabilistic, uncertainty-aware siting

Propagating the MEF bootstrap CIs into the ranking (Monte-Carlo) gives each BA a *rank distribution*, not a point rank.

| BA | MEF | mean rank | P(top-5) | P(rank 1) |
|---|---:|---:|---:|---:|
| BPAT | 7 | 1.0 | 1.00 | 0.97 |
| PACW | 10 | 2.0 | 1.00 | 0.03 |
| IPCO | 22 | 3.0 | 1.00 | 0.00 |
| PGE | 51 | 4.1 | 1.00 | 0.00 |
| LDWP | 71 | 5.2 | 0.76 | 0.00 |
| AZPS | 94 | 6.6 | 0.18 | 0.00 |

**2 BA pairs are statistically indistinguishable** (P(greener) in [0.4, 0.6]) — their 'greener' verdict is a coin flip given MEF uncertainty. Point rankings hide this; siting should prefer BAs robustly greener across the CI.

## Thrust 1a: short-run dispatch margin vs long-run build margin (Cambium LRMER)

A 15+ year data center induces new capacity, so its true signal is the **long-run** marginal (NREL Cambium LRMER, kg CO2e/MWh, Mid-case, 2025-2030), not the short-run dispatch margin (our Siler-Evans MEF). They re-rank BAs.

| BA | short-run MEF | long-run LRMER | rank(SR) | rank(LR) | shift |
|---|---:|---:|---:|---:|---:|
| BPAT | 7 | 96 | 1 | 1 | +0 |
| PGE | 51 | 96 | 4 | 1 | +3 |
| PACW | 10 | 96 | 2 | 1 | +1 |
| CISO | 142 | 107 | 10 | 4 | +6 |
| LDWP | 71 | 107 | 5 | 4 | +1 |
| NYIS | 255 | 114 | 14 | 6 | +8 |
| ISNE | 331 | 133 | 19 | 7 | +12 |
| ERCO | 256 | 184 | 15 | 8 | +7 |
| MISO | 579 | 208 | 25 | 9 | +16 |
| PSCO | 98 | 223 | 7 | 10 | -3 |
| WACM | 164 | 223 | 11 | 10 | +1 |
| PJM | 400 | 236 | 21 | 12 | +9 |
| NEVP | 132 | 241 | 9 | 13 | -4 |
| PNM | 263 | 244 | 16 | 14 | +2 |
| AZPS | 94 | 244 | 6 | 14 | -8 |
| SRP | 173 | 244 | 12 | 14 | -2 |
| AECI | 526 | 247 | 24 | 17 | +7 |
| SWPP | 599 | 257 | 26 | 18 | +8 |
| PACE | 121 | 262 | 8 | 19 | -11 |
| TVA | 219 | 273 | 13 | 20 | -7 |
| DUK | 352 | 273 | 20 | 20 | +0 |
| CPLE | 311 | 273 | 18 | 20 | -2 |
| SOCO | 435 | 273 | 23 | 20 | +3 |
| LGEE | 694 | 273 | 27 | 24 | +3 |
| IPCO | 22 | 284 | 3 | 25 | -22 |
| FPL | 294 | 306 | 17 | 26 | -9 |
| FPC | 426 | 306 | 22 | 26 | -4 |

Biggest re-rankers short-run→long-run: **IPCO** (-22), **MISO** (+16), **ISNE** (+12), **PACE** (-11), **FPL** (-9). Hydro-rich BAs look greenest short-run (their extra MWh is existing hydro) but their *long-run* margin is high (new load induces fossil capacity, not new hydro) — the consequential inversion (Gagnon/Ricks/Jenkins). Cambium: Gagnon et al., nrel.gov/analysis/cambium.html.

## Thrust 1b: is the marginal factor 'sticky'? (Holland et al. reproduction)

Holland et al. (2022, PNAS) found US *marginal* CO2 has not fallen as fast as *average*. We test it per BA over 2019-present (annual AEF & MEF trends, kg/MWh/yr).

| BA | yrs | AEF trend | MEF trend | stickiness (MEF/AEF) |
|---|---:|---:|---:|---:|
| PJM | 8 | -6.9 | +50.4 | -7.35 |
| ISNE | 8 | +3.6 | -8.0 | -2.22 |
| BPAT | 8 | -2.4 | -1.5 | 0.62 |
| SOCO | 8 | -9.2 | -9.1 | 0.98 |
| MISO | 8 | -16.1 | -25.5 | 1.58 |
| CISO | 8 | -16.0 | -27.1 | 1.69 |
| SWPP | 8 | -14.4 | -27.7 | 1.93 |
| ERCO | 8 | -18.4 | -62.1 | 3.38 |

In **4 of 8 BAs the marginal factor is stickier than the average** (ratio < 1): renewables cut the average while gas still sets the margin — reproducing Holland et al. on independent live data. Ref: doi:10.1073/pnas.2116632119.

## Thrust 2: intra-BA nodal marginal carbon (CAISO)

Two sites in the *same* BA face different marginal carbon under congestion. Using CAISO OASIS nodal LMP decomposition (public, no-auth) over representative days:

- Nodes analyzed: **2459**; congested (|mean MCC|>$1): **1740**
- BA system marginal factor (EIA-930): **142 kg/MWh**
- Directional nodal marginal-carbon index spans **89–202 kg/MWh** (p10–p90), i.e. ±~50% around the BA average

The cleanest nodes are export-constrained **solar** buses (local spilled solar sets the margin); the dirtiest are import-constrained load pockets. BA-average MEF erases this. *Exact* nodal kg/MWh needs CEII shift factors (proprietary); the congestion spread and direction are what public data supports (doi:10.1088/2753-3751/ad72f6).

## Thrust 6 (capstone): the siting recommendation is not robust

A per-BA carbon factor is computed under **6 specifications** crossing temporal (short/long-run), accounting (production/consumption), and method (regression/instrument/Cambium), then BAs are ranked under each (`spec_curve.png`).

Specifications: *AEF (avg, prod, BA)*; *MEF short-run prod (regression)*; *MEF short-run prod (VRE instrument)*; *MEF short-run consumption (flow-trace)*; *LRMER long-run (Cambium)*; *SRMER short-run (Cambium model)*.

**24 of 27 balancing authorities flip** their siting rank materially across specifications. Only **2 are robustly green** (BPAT, PACW) and **1 robustly dirty**. The biggest flipper, **IPCO**, ranges rank 3→25 on accounting choice alone.

**The recommendation is far less robust than single-metric analyses imply.** Only hydro-dominated regions are unambiguous; elsewhere the accounting choice determines the answer. Method: specification-curve analysis (Simonsohn et al. 2020, doi:10.1038/s41562-020-0912-z).

| BA | specs | mean rank | min | max | verdict |
|---|---:|---:|---:|---:|---|
| BPAT | 6 | 1.2 | 1 | 2 | robust-green |
| PACW | 6 | 2.0 | 1 | 3 | robust-green |
| CISO | 6 | 4.2 | 1 | 10 | flips |
| PGE | 5 | 5.0 | 1 | 15 | flips |
| LDWP | 6 | 7.8 | 4 | 17 | flips |
| NYIS | 5 | 10.0 | 6 | 16 | flips |
| ERCO | 6 | 10.5 | 8 | 15 | flips |
| PSCO | 6 | 10.5 | 7 | 16 | flips |
| IPCO | 6 | 11.0 | 3 | 25 | flips |
| PNM | 6 | 11.0 | 5 | 16 | flips |
| NEVP | 6 | 11.5 | 9 | 14 | flips |
| SRP | 6 | 11.7 | 6 | 15 | flips |
| ISNE | 5 | 12.2 | 7 | 19 | flips |
| AZPS | 6 | 12.5 | 6 | 21 | flips |
| CPLE | 6 | 15.7 | 7 | 21 | flips |
| PACE | 6 | 15.8 | 5 | 24 | flips |
| PJM | 6 | 16.0 | 12 | 21 | flips |
| WACM | 6 | 16.0 | 10 | 25 | flips |

## Build 2 (Thrust 7): state-dependent autoregressive MEF

A fourth, more principled MEF estimator: a per-BA two-regime Markov-switching model with an autoregressive term and generation regressors (MS-ARX(1)). The marginal factor is the coefficient on non-renewable generation and is *regime-specific*; we report both regime MEFs and the ergodic-probability-weighted scalar (fed into Build 1's ambiguity set). Driven off hourly generation, not load, so imported carbon is not misattributed to local marginal units. Spec: Panico, Burlinson & Grossi (2026, arXiv:2603.04260); AR-MEF precedent Beltrami et al. (2020, Energy Economics 91:104905, doi:10.1016/j.eneco.2020.104905).

Fit converged for **22 of 27 BAs** (the rest hit singular fits, typically very clean or storage/import-dominated systems).

| BA | Siler-Evans | VRE-ramp | state-AR (erg.) | low regime | high regime | regime spread % | 3-way spread % |
|---|---:|---:|---:|---:|---:|---:|---:|
| FPC | 426 | 425 | 383 | 373 | 407 | 9 | 0 |
| PJM | 400 | 414 | 260 | 249 | 533 | 109 | 3 |
| SWPP | 599 | 567 | 482 | 476 | 487 | 2 | 5 |
| MISO | 579 | 496 | 380 | 380 | 601 | 58 | 15 |
| PGE | 51 | — | 283 | 59 | 413 | 125 | 38 |
| FPL | 294 | 440 | 401 | 359 | 424 | 16 | 40 |
| ERCO | 256 | 385 | 390 | 355 | 421 | 17 | 51 |
| DUK | 352 | 632 | 164 | 164 | 164 | 0 | 57 |
| CPLE | 311 | 145 | 226 | 200 | 247 | 21 | 73 |
| TVA | 219 | 503 | 43 | 42 | 746 | 1633 | 79 |
| SRP | 173 | 428 | 220 | 85 | 304 | 100 | 95 |
| AECI | 526 | 138 | 519 | 460 | 563 | 20 | 117 |
| CISO | 142 | 25 | 186 | 34 | 403 | 199 | 141 |
| IPCO | 22 | 42 | 179 | 18 | 427 | 228 | 161 |
| PSCO | 98 | 398 | 335 | 294 | 375 | 24 | 218 |
| PNM | 263 | 70 | 184 | 48 | 368 | 174 | 245 |
| PACE | 121 | 542 | 788 | 775 | 800 | 3 | 303 |
| LDWP | 71 | 299 | 212 | 125 | 494 | 174 | 360 |
| BPAT | 7 | -2 | 64 | 1 | 411 | 641 | 368 |
| NEVP | 132 | 241 | 377 | 199 | 479 | 74 | 847 |
| ISNE | 331 | — | 261 | 148 | 307 | 61 | — |
| NYIS | 255 | — | 314 | 90 | 318 | 72 | — |

**Triangulation convergence within 20%: 6/24 with three methods, 3/26 with the state-AR added -- a principled fourth estimator does not improve agreement.** The short-run margin stays method-dependent; a single scalar MEF is not recoverable for most BAs.

**Why: the margin is genuinely state-dependent.** Most fitted BAs carry two materially different regime MEFs (a low, gas-like regime and a high, coal-like regime). The median regime spread is 87% for BAs where the 3-way triangulation diverges versus 34% where it converges -- the BAs with no agreed single MEF are largely those whose marginal unit switches regime. The link is in the central tendency, not linear (corr(regime spread, 3-way spread) = 0.03; heavy-tailed). Either way this supports the fragility thesis: the object the siting literature ranks on is not a well-defined scalar for most BAs. Ref: Environ. Res.: Energy 2024, doi:10.1088/2753-3751/ad72f6.

## Build 1: robust siting under accounting-method ambiguity (min-max regret)

The multiverse shows the siting rank flips across accounting methods. Instead of committing to one method, choose the site that minimises worst-case *regret* over the whole ambiguity set of 6 marginal methods: regret(r,m) = c_m(r) - min_r' c_m(r'); the robust site is argmin_r max_m regret(r,m). Min-max regret over a discrete scenario set: Aissi, Bazgan & Vanderpooten (2009, EJOR 197:427); Bertsimas & Sim (2004, Oper. Res. 52:35); Ben-Tal, El Ghaoui & Nemirovski (2009). Precedent for min-max regret across competing models: Rezai & van der Ploeg (2017, Energy Economics 68:4).

Ambiguity set: MEF short-run prod (regression), MEF short-run prod (VRE instrument), MEF short-run consumption (flow-trace), LRMER long-run (Cambium), SRMER short-run (Cambium model), AR-MEF short-run (state-dependent).

**Min-max-regret site: BPAT** -- worst-case regret 20.9 kg/MWh (binding method: AR-MEF short-run (state-dependent)) versus 57 kg/MWh for the runner-up PACW. **The low-regret core (within 10% of optimal on every method) is {BPAT, PACW}** -- exactly the Pacific-NW hydro set the specification curve flags as robust-green. The decision rule reproduces the robust core constructively; it is the only set a developer can build in without betting on the accounting choice.

**Price of robustness at BPAT** (regret vs each method's own optimum, kg/MWh):

| method | regret |
|---|---:|
| AR-MEF short-run (state-dependent) | 20.92 |
| MEF short-run consumption (flow-trace) | 2.45 |
| MEF short-run prod (regression) | 0.00 |
| MEF short-run prod (VRE instrument) | 0.00 |
| LRMER long-run (Cambium) | 0.00 |
| SRMER short-run (Cambium model) | 0.00 |

So BPAT is optimal or near-optimal under every method -- at most 20.9 kg/MWh worse than the best possible under any single accounting choice, near-free insurance against the accounting choice.

**Worst-case regret, best 8 regions (kg/MWh):**

| BA | max regret | binding method | mean regret | n methods |
|---|---:|---|---:|---:|
| BPAT | 20.9 | AR-MEF short-run (state-dependent) | 3.9 | 6 |
| PACW | 57.1 | MEF short-run consumption (flow-trace) | 18.2 | 5 |
| CISO | 142.7 | AR-MEF short-run (state-dependent) | 54.4 | 6 |
| IPCO | 188.3 | LRMER long-run (Cambium) | 116.4 | 6 |
| PGE | 239.4 | AR-MEF short-run (state-dependent) | 72.8 | 5 |
| PNM | 256.0 | MEF short-run prod (regression) | 168.5 | 6 |
| AZPS | 272.5 | MEF short-run consumption (flow-trace) | 154.8 | 5 |
| LDWP | 301.7 | MEF short-run prod (VRE instrument) | 117.1 | 6 |

**Hedge (Rule B).** Best two-region hedge: **BPAT+PACW** (worst-case regret 2.4 kg/MWh, rank-corr 0.56), taking the better of the two under each method. With the hydro core unavailable, best hedge: **PGE+TVA** (worst-case regret 80.4 kg/MWh, rank-corr -0.99).

**Uncertainty (10x).** Replacing the regression MEF with 300 bootstrap draws (min-max over method choice AND estimation error), the robust site BPAT survives in 100% of draws and the low-regret core in 100%; the verdict is insensitive to estimation error (reference-prior Bayesian draws agree).
