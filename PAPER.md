# Carbon-optimal data-center siting is not robust to the carbon-accounting choice: a specification-curve analysis on live grid data

*Draft preprint. Target: arXiv eess.SY / econ.EM. Artifact: gridpulse (this repo), reproducible from zero.*

## Abstract

The surge in data-center load has made "where should the next data center go to
minimize carbon?" a live policy question, usually answered by ranking regions on a
single emission factor. **Our single claim: that ranking — and therefore the
carbon-optimal siting recommendation — is not robust to the carbon-accounting
choice.** Using two years of hourly EIA-930 data for 27 US balancing authorities
(BAs) across all three interconnects, with the computed average factor validated
against EIA's own published hourly CO2 to a median of 1.6% for fossil-dominated
BAs, we compute a per-BA carbon factor under a *multiverse* of defensible
accounting choices spanning four axes: temporal (short-run dispatch vs long-run
build margin), accounting boundary (production vs consumption/import-adjusted),
spatial resolution (BA vs nodal), and estimation method (regression vs supply-side
instrument vs capacity-expansion model). Across six specifications, **24 of 27 BAs
change siting rank and only 3 are robust** (two Pacific-Northwest hydro BAs
robustly green, one coal BA robustly dirty). The re-rankings are not cosmetic: the
median flipping BA moves 12 ranks, 10 BAs span at least half the fleet, and four
undergo outright inversions — Idaho Power (IPCO) runs from rank 3 (near-greenest,
short-run) to 25 (near-worst, long-run). The short-run marginal factor is itself
hard to identify: three independent supply-side estimators converge within 20% for
only 6 of 23 BAs, which we read as evidence *for* the fragility thesis — the margin
is genuinely ill-defined outside a single-fossil-unit regime — not as validation.
We turn the critique into a decision rule: site where the verdict is robust across
all accounting choices (the Pacific-NW hydro core), or, where that core is
unavailable, hedge across regions whose rank vectors are anti-correlated
(IPCO+MISO, rank-correlation −0.93, caps worst-case rank at 9 versus 25 for either
site alone). All numbers regenerate from the released `gridpulse` pipeline.

## 1. Introduction

A new data center is an increment of load that persists for 15+ years. Its climate
impact is therefore governed by the grid's **marginal** response, not its average —
a point established since Siler-Evans et al. (2012). The policy literature and
commercial siting tools translate this into a ranking: order BAs by a carbon
factor, site in the low-carbon ones. **We show that ranking is not robust.** "The
marginal factor" hides four choices, each contested at the research frontier and
each capable of inverting which region is "greenest":

1. **Temporal horizon.** The short-run *dispatch* margin (which existing unit
   ramps) differs from the long-run *build* margin (what new capacity the load
   induces). Short-run-optimal operation can raise long-run emissions
   (Gagnon & Cole 2022); marginal factors have not fallen as fast
   as average factors (Holland et al. 2022).
2. **Accounting boundary.** Production-based emissions ignore that a BA may serve
   load with dirty imports; consumption-based (import-adjusted) accounting via
   interchange flow-tracing (de Chalendar et al. 2019) re-ranks regions.
3. **Spatial resolution.** Two nodes in the same BA face different marginal carbon
   under transmission congestion; BA-average erases this.
4. **Estimation method.** Regression (Siler-Evans), dispatch/instrumental
   estimates, and capacity-expansion models (NREL Cambium) need not agree.

Our contribution is a single, sharp claim answered with a specification-curve
(multiverse) analysis (Simonsohn, Simmons & Nelson 2020): **a carbon-optimal siting
recommendation is meaningless without the accounting choice that produced it, and
the set of sites that are good under *every* choice is small.** We build and
validate each method on live data, release the full pipeline as `gridpulse`, and
close with a decision rule that follows directly from the fragility we measure.

## 2. Data

- **EIA-930 hourly** fuel mix, demand, and BA-to-BA interchange for 27 balancing
  authorities across all three interconnects, via the EIA API v2. 24 months at
  full coverage; 2019-present for a subset (Holland test). These 27 are a
  **truncation of the ~66-BA EIA interchange network** (see §6).
- **EIA Hourly Electric Grid Monitor** per-BA workbooks — EIA's *published* hourly
  CO2, used as validation ground truth (not self-consistency).
- **NREL Cambium** long-run marginal emission rates (LRMER), GEA-region resolution,
  forward scenarios.
- **CAISO OASIS** nodal LMP with congestion decomposition (no-auth, reproducible),
  for the intra-BA nodal analysis.
- **FracTracker** national data-center tracker (per-facility MW + location).

## 3. Methods

- **AEF**: Σ CO2 / Σ generation, on EIA's production basis (fossil combustion only:
  COL, NG, OIL), validated against EIA's published hourly CO2.
- **Short-run MEF**: Siler-Evans OLS of ΔCO2 on Δdemand over consecutive hours,
  bootstrap CIs; recovers a planted margin to machine precision on synthetic data.
- **Consumption MEF**: emissions flow-tracing over the interchange network
  (de Chalendar 2019 linear system), then a marginal factor on the import-adjusted
  series. Runs on the 27-BA modeled subnetwork; imports across cut edges are
  dropped (§6).
- **Supply-side instruments** (identification stress-test): (i) VRE-ramp — carbon
  displaced per MWh of exogenous wind/solar with demand held flat; (ii)
  generation-trip — emissions response to detected forced outages.
- **State-dependent AR-MEF**: a two-regime Markov-switching model with an
  autoregressive term and generation regressors (MS-ARX(1); Panico, Burlinson &
  Grossi 2026), fit per BA. The marginal factor is the regime-specific coefficient
  on non-renewable generation; we summarise it by the ergodic-probability-weighted
  MEF. It extends the autoregressive MEF of Beltrami et al. (2020) and, like the
  rest of gridpulse, drives off hourly generation rather than load.
- **Nodal LME**: CAISO nodal congestion component modulating the BA system margin
  (directional only; exact nodal kg/MWh requires proprietary CEII shift factors).
- **Long-run**: NREL Cambium LRMER/SRMER, mapped GEA-region → BA.
- **Specification curve**: rank BAs under every (temporal × accounting × spatial ×
  method) combination; classify each BA robust-green / robust-dirty / flips by its
  rank range across specifications.

## 4. Results

Generated by the live run (`gridpulse phase3`); tables in FINDINGS.md/EVIDENCE.md,
committed rank matrix in `data/multiverse_ranks.csv` and robustness classification
in `data/multiverse_robustness.csv`, multiverse figure in `docs/figs/spec_curve.png`.

- **4.1 Validation (of the pipeline, not the thesis).** Computed AEF matches EIA's
  *published* hourly CO2 to a median of **1.6%** across fossil-dominated BAs using
  EIA's own per-fuel factors (ERCO −2.4%, MISO −0.6%, DUK −5.4%, SOCO −1.5%). This
  anchors the average-factor pipeline before any marginal analysis; it says nothing
  about how well-identified the *marginal* factor is (see 4.2).
- **4.2 The short-run margin is hard to identify — evidence for fragility.**
  Siler-Evans, the VRE-ramp instrument, and generation-trip events converge within
  20% for **only 6 of 23 BAs** (FPC, PJM, SWPP, SOCO, MISO, AZPS) — exactly those
  where a single fossil unit sets the margin. In storage/solar/import-heavy systems
  the three estimates diverge by 100–800% (CISO 141%, WACM 573%, NEVP 847%),
  because batteries and imports break the one-margin assumption. We do **not** read
  6/23 as validation of the MEF. It is direct evidence that the object the siting
  literature ranks on is genuinely ill-defined for three-quarters of the fleet — a
  first-order reason the downstream ranking is fragile. Adding a fourth,
  state-dependent estimator does not reconcile them: a Markov-switching AR MEF
  (MS-ARX; §3) fit per BA leaves 20%-convergence at **3 of 26** and reveals *why*
  — most BAs carry two very different regime marginal factors (median regime
  spread **87%** among the BAs where the three supply-side estimators already
  diverge, versus 34% where they agree). The short-run margin is genuinely
  state-dependent, so there is no single scalar MEF to converge on.
- **4.3 Consumption re-ranking.** Import-adjusted (flow-traced) marginal carbon
  moves several BAs 10+ ranks versus production-based (CPLE −14, PGE +11, ISNE −10).
- **4.4 Nodal.** Within CISO, congestion spreads the directional marginal-carbon
  index **±~50%** around the BA-average (p10–p90 ≈ 89–202 kg/MWh vs 142 system);
  cleanest nodes are export-constrained **solar** buses, dirtiest are import-
  constrained load pockets — variation BA-resolution erases entirely.
- **4.5 Short-run vs long-run.** Ranking under NREL Cambium **LRMER** (long-run) vs
  our short-run MEF flips hydro-rich BAs hardest: **IPCO shifts −22 ranks** (rank 3
  short-run — its extra MWh is existing hydro; rank 25 long-run — new load induces
  fossil capacity), MISO +16, ISNE +12, PACE −11, FPL −9. Separately, reproducing
  Holland et al. (2022) on 2019–2025 data, **4 of 8 BAs show the marginal factor
  falling more slowly than the average** (stickiness < 1): renewables cut the
  average while gas still sets the margin.
- **4.6 Multiverse (headline).** Across six specifications — AEF; short-run
  production MEF (regression); short-run production MEF (VRE instrument); short-run
  consumption MEF (flow-trace); long-run LRMER (Cambium); short-run SRMER (Cambium)
  — **24 of 27 BAs change siting rank; only 3 are robust**: BPAT (rank range 1–2)
  and PACW (1–3) robustly green, LGEE (24–27) robustly dirty. **Distribution of the
  24 flips by rank range** (max − min across specs; median 12 of a 27-BA fleet):

  | flip magnitude | n | BAs (rank range) |
  |---|---:|---|
  | minor (≤5 ranks) | 1 | NEVP (5) |
  | moderate (6–10) | 9 | NYIS 10, CISO 9, PSCO 9, SRP 9, PJM 9, SWPP 8, ERCO 7, TVA 7, SOCO 6 |
  | large (11–15) | 10 | AZPS 15, WACM 15, PGE 14, CPLE 14, FPL 14, LDWP 13, ISNE 12, DUK 12, FPC 12, PNM 11 |
  | inversion (>15) | 4 | **IPCO 22 (3→25)**, PACE 19 (5→24), AECI 19 (7→26), MISO 16 (9→25) |

  So the headline is not a uniform reshuffle: 10 of the 24 flippers span **at least
  half the fleet** (range ≥13), and four are outright inversions where a BA moves
  from the greenest quartile to the dirtiest (or vice versa) on the accounting
  choice alone. Only the Pacific-NW hydro core is unambiguous.

## 5. Discussion

The carbon-optimal siting recommendation is contingent on the analyst's accounting
choices to a degree that undermines single-metric guidance. The robust policy
signal is narrow — Pacific-NW hydro — and everywhere else the verdict depends on
whether one prices short- or long-run carbon, production or consumption, BA-average
or nodal, and by which estimator. Siting policy and 24/7-CFE procurement
(Ricks, Xu & Jenkins 2023) should therefore report the accounting choice explicitly
and prefer regions robust across the multiverse. §5.1 makes this actionable.

### 5.1 A decision rule under fragility

Fragility is not a dead end for a developer; it prescribes two concrete strategies,
both computed from the committed multiverse output.

**Rule A — site where the verdict is robust.** Only BPAT and PACW are green under
*every* one of the six accounting choices (rank ranges 1–2 and 1–3). A
recommendation to build there carries no accounting caveat. Concentrating a
carbon-optimal 10 GW build-out in the low-carbon set — respecting a
20%-of-local-demand deliverability cap per BA — avoids **≈25.2 MtCO2/yr (76%** of
the tracked build-out's marginal emissions) on the production-marginal basis (best
site BPAT at 7.4 kg/MWh; `data/gap.json`). This payoff is itself
accounting-dependent — **31.7 MtCO2/yr** on the consumption-marginal basis — which
is the point: even the *size of the prize* moves with the accounting choice, so the
robust core is where a developer captures it without betting on which choice is
right.

**Rule B — hedge across anti-correlated regions.** Where the hydro core is
unavailable (deliverability, land, water, latency), split load across a pair of BAs
whose rank vectors across the six specifications are anti-correlated, so the
portfolio is insensitive to which accounting choice ultimately governs. The
cleanest case is the temporal axis: **IPCO** (rank 3–6 short-run, 25 long-run) and
**MISO** (25 short-run, 9 long-run) have a rank-vector correlation of **−0.93**; a
developer able to take the better of the two under whichever horizon prices the
carbon is **never worse than rank 9**, versus rank 25 for a single-site commitment.
On the production-vs-consumption axis, **PNM+WACM** (correlation **−0.96**) cap the
worst-case rank at 12 versus 25 for WACM alone. (This assumes load can shift between
the paired sites and that the measured anti-correlation persists out of sample; the
correlation is computed over the six specifications, not forecast.)

### 5.2 Robust siting as min-max regret

§5.1's rules follow from one optimisation. Treat the set of defensible accounting
methods as an ambiguity set M — the six marginal methods (short-run regression
MEF, VRE-instrument MEF, consumption MEF, Cambium LRMER, Cambium SRMER, and the
state-dependent AR-MEF of §3) — each assigning a carbon cost c_m(r) to a fixed
candidate load in region r. Define regret(r,m) = c_m(r) − min_r' c_m(r') and
choose the site that minimises worst-case regret, r\* = argmin_r max_m regret(r,m)
(min-max regret over a discrete scenario set; Aissi, Bazgan & Vanderpooten 2009;
Bertsimas & Sim 2004; Ben-Tal, El Ghaoui & Nemirovski 2009).

The min-max-regret site is **BPAT**, with a worst-case regret of **20.9 kg/MWh**
(binding method: the AR-MEF) against **57 kg/MWh** for the runner-up PACW. BPAT is
the outright optimum under four of the six methods and within 2.4 kg/MWh under a
fifth, so its *price of robustness* — the most it can trail the best site under
any single accounting choice — is small against factors that range past
800 kg/MWh. No site achieves uniformly zero regret, though: even BPAT trails the
cleanest region under the state-dependent AR-MEF by 20.9 kg/MWh (0.18 MtCO2/yr for
a 1 GW load). All six methods are carbon intensities on a common kg/MWh basis, so a
fixed candidate load rescales them identically to MtCO2/yr and this gap is genuine,
not a units artifact — robustness here is a minimised worst case, not its
elimination. The **low-regret core** (regions within 10% of each method's spread of
optimal on *every* method) is exactly **{BPAT, PACW}**, recovering the
specification curve's robust-green set from an optimisation rather than a
classification. Propagating the regression-MEF estimation uncertainty (bootstrap
and reference-prior Bayesian draws) leaves the min-max-regret site and the
low-regret core unchanged in ~100% of draws: the verdict is robust to *both* the
accounting method and estimation error. Where the hydro core is unavailable, the
same objective selects a two-region hedge among the remaining BAs (an
anti-correlated pair, rank correlation ≈ −0.99), formalising Rule B.

This is, to our knowledge, the first treatment of carbon-accounting-**method**
ambiguity as the scenario set for robust siting. It is distinct from the robust
and distributionally-robust data-center literature, which hedges *physical*
uncertainty — renewable output and workload (Han et al. 2025, 2026) or wind in
data-center/grid co-planning (Dong et al. 2024). It is the constructive
counterpart to empirical demonstrations that the accounting choice changes carbon
decisions (Maji et al. 2024, "The Green Mirage"), and it transplants min-max
regret over competing *models* (Rezai & van der Ploeg 2017, over DICE/FUND/PAGE)
to competing accounting *methods*. We claim neither robustness to physical
uncertainty nor a new estimator of the "true" MEF; the contribution is the
decision rule and the empirically-computed robust core.

## 6. Limitations

- **Subnetwork truncation (primary exposure).** All results hold **within the 27-BA
  modeled subnetwork**, a truncation of the ~66-BA EIA interchange network.
  Flow-tracing (§3) is solved on this subnetwork, so edges to unmodeled BAs are cut
  and imports across them are dropped. This is why the consumption MEF is **floored
  at 0** for solar-saturated, strongly import-dependent BAs (CISO): with the import
  edges removed, the raw import-adjusted estimate dips physically-impossibly
  negative and is clipped to the non-negative minimum. **Direction of bias:** the
  floor makes such BAs look artificially clean on the consumption specification,
  which *widens* their measured rank range (CISO reaches rank 1 on the consumption
  spec vs rank 10 on regression MEF). The truncation therefore, if anything,
  **overstates the flip magnitude for import-dependent BAs**; restoring the omitted
  (largely fossil) out-of-subnetwork imports would raise their consumption factors
  and *narrow* those particular flips. It does **not** manufacture the flip — CISO
  already re-ranks on the production bases alone — and it does **not** touch the
  robust core: BPAT and PACW are net hydro *exporters*, not import-sensitive. So the
  central claim (a small robust set; most BAs contingent) is conservative to this
  bias, while specific solar-BA flip magnitudes should be read as upper bounds. A
  full ~66-BA solve is the natural next step.
- **Short-run vs long-run dependence.** Our short-run MEF is a dispatch-margin
  estimate; Cambium LRMER is the long-run build margin. The IPCO 3→25 inversion is
  driven entirely by this axis, so any headline flip involving it inherits the
  short-run/long-run modeling assumptions and is not a single ground-truth number.
- **Cambium scenario dependence.** The long-run results use Cambium's Mid-case,
  2025–2030 vintage. LRMER/SRMER are model- and scenario-dependent; a different
  scenario (high-renewable, high-gas) would move the long-run ranks and could change
  which BAs invert.
- **Nodal estimates are directional only.** The nodal LME is a congestion-based
  *index*; an exact nodal kg/MWh needs proprietary/CEII shift factors and offer
  stacks that are not public. We report spread and direction, not levels, and there
  is **no nodal ground truth** to validate against.
- **MEF identification** degrades in storage/solar/import-heavy BAs (§4.2; shown,
  not hidden) — the short-run margin is well-identified in only 6 of 23 BAs.
- Two-year primary window; longer history (2019–present) only for the 8-BA subset
  used in the Holland test.

## 7. Reproducibility

All results regenerate from zero via `gridpulse` (`pip install -e ".[prod]"`;
`pytest`; the CLI + `phase3` orchestrator). Data sources are public; the only
credential is a free EIA API key. CI runs the live refresh monthly. Cite via
`CITATION.cff` (Zenodo DOI on release).

## References

- Siler-Evans, Azevedo & Morgan (2012). Marginal emissions factors for the US
  electricity system. *Environ. Sci. Technol.* 46(9):4742. doi:10.1021/es300145v.
- de Chalendar, Taggart & Azevedo (2019). Tracking emissions in the US electricity
  system. *PNAS* 116(51):25497. doi:10.1073/pnas.1912950116.
- Holland, Kotchen, Mansur & Yates (2022). Why marginal CO2 emissions are not
  decreasing for US electricity. *PNAS* 119(37):e2116632119.
  doi:10.1073/pnas.2116632119.
- Gagnon, P. & Cole, W. (2022). Planning for the evolution of the electric grid with
  a long-run marginal emission rate. *iScience* 25(3):103915.
  doi:10.1016/j.isci.2022.103915.
- Ricks, W., Xu, Q. & Jenkins, J. D. (2023). Minimizing emissions from grid-based
  hydrogen production in the United States. *Environ. Res. Lett.* 18(1):014025.
  doi:10.1088/1748-9326/acacb5.
- Simonsohn, Simmons & Nelson (2020). Specification curve analysis. *Nature Human
  Behaviour* 4:1208. doi:10.1038/s41562-020-0912-z.
- NREL Cambium (Gagnon et al.). https://www.nrel.gov/analysis/cambium.html
- Steinsultz, N., Christian, P., Cofield, J., McCormick, G. & Sofia, S. (2024).
  Validating locational marginal emissions models with wind generation.
  *Environ. Res.: Energy* 1(3). doi:10.1088/2753-3751/ad72f6.
- Aissi, H., Bazgan, C. & Vanderpooten, D. (2009). Min-max and min-max regret
  versions of combinatorial optimization problems: A survey. *European Journal of
  Operational Research* 197(2):427–438. doi:10.1016/j.ejor.2008.09.012.
- Bertsimas, D. & Sim, M. (2004). The price of robustness. *Operations Research*
  52(1):35–53. doi:10.1287/opre.1030.0065.
- Ben-Tal, A., El Ghaoui, L. & Nemirovski, A. (2009). *Robust Optimization*.
  Princeton University Press. ISBN 978-0-691-14368-2.
- Rezai, A. & van der Ploeg, F. (2017). Climate policies under climate model
  uncertainty: Max-min and min-max regret. *Energy Economics* 68:4–16.
  doi:10.1016/j.eneco.2017.10.018.
- Panico, A., Burlinson, A. & Grossi, L. (2026). State-dependent marginal emission
  factors with autoregressive components. *arXiv* 2603.04260.
  doi:10.48550/arXiv.2603.04260.
- Beltrami, F., Burlinson, A., Giulietti, M., Grossi, L., Rowley, P. & Wilson, G.
  (2020). Where did the time (series) go? Estimation of marginal emission factors
  with autoregressive components. *Energy Economics* 91:104905.
  doi:10.1016/j.eneco.2020.104905.
- Han, J., Han, K., Han, T., Wang, Y., Han, Y. & Lin, J. (2025). Data-driven
  distributionally robust optimization of low-carbon data center energy systems
  considering multi-task response and renewable energy uncertainty. *Journal of
  Building Engineering* 102:111937. doi:10.1016/j.jobe.2025.111937.
- Han, J., Tong, N., Lin, J., Han, Y., Wang, Y., Han, K. & Li, Y. (2026).
  Distributionally robust co-optimization of computing workloads and renewable
  energy uncertainties in geo-distributed data centers. *Energy Conversion and
  Management: X* 29:101432. doi:10.1016/j.ecmx.2025.101432.
- Dong, H., Wang, L., Zhang, X. & Zeng, M. (2024). A two-stage stochastic
  collaborative planning approach for data centers and distribution network
  incorporating demand response and multivariate uncertainties. *Journal of
  Cleaner Production* 451:141482. doi:10.1016/j.jclepro.2024.141482.
- Maji, D., Bashir, N., Irwin, D., Shenoy, P. & Sitaraman, R. K. (2024). The Green
  Mirage: Impact of location- and market-based carbon intensity estimation on
  carbon optimization efficacy. *arXiv* 2402.03550. doi:10.48550/arXiv.2402.03550.
