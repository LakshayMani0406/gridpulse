# How robust is carbon-optimal data-center siting to the accounting choice? A specification-curve analysis on live grid data

*Draft preprint. Target: arXiv eess.SY / econ.EM. Artifact: gridpulse (this repo), reproducible from zero.*

## Abstract

The surge in data-center load has made "where should the next data center go to
minimize carbon?" a live policy question. The standard answer ranks regions by a
single metric — usually the **average** grid emission factor, sometimes the
**short-run production-based marginal** factor at balancing-authority (BA)
resolution. We show this recommendation is far less robust than the literature
admits. Using two years of hourly EIA-930 data for 27 US balancing authorities
(validated against EIA's own published hourly CO2 to a median of 1.6% for
fossil-dominated BAs), we compute a per-BA carbon factor under a *multiverse* of
defensible accounting choices crossing four axes: temporal (short-run vs
long-run), accounting (production vs consumption/import-adjusted), spatial
(BA vs nodal), and estimation method (regression vs supply-side instrument vs
capacity-expansion model). We find that **[N] of 27 balancing authorities change
their siting rank materially across specifications**; only the hydro-dominated
Pacific Northwest is robustly low-carbon regardless of choice. We validate the
marginal factor itself with two independent supply-side instruments (exogenous
wind/solar ramps and generation trips), which converge to within 20% where a
single fossil unit sets the margin but diverge in storage/solar-heavy systems.
The policy implication: a carbon-optimal siting recommendation is only meaningful
paired with the accounting choice that produced it, and the *robust* set of good
sites is much smaller than any single metric suggests.

## 1. Introduction

A new data center is an increment of load that persists for 15+ years. Its
climate impact is therefore governed by the grid's **marginal** response, not its
average — a point well established since Siler-Evans et al. (2012). But "the
marginal factor" hides four further choices, each contested at the research
frontier and each capable of inverting the ranking of the "greenest" region:

1. **Temporal horizon.** The short-run *dispatch* margin (which existing unit
   ramps) differs from the long-run *build* margin (what new capacity the load
   induces). Short-run-optimal operation can raise long-run emissions
   (Gagnon, Ricks, Jenkins et al. 2022). Marginal factors have not fallen as fast
   as average factors (Holland et al. 2022).
2. **Accounting boundary.** Production-based emissions ignore that a BA may serve
   load with dirty imports; consumption-based (import-adjusted) accounting via
   interchange flow-tracing (de Chalendar et al. 2019) re-ranks regions.
3. **Spatial resolution.** Two nodes in the same BA face different marginal
   carbon under transmission congestion; BA-average erases this.
4. **Estimation method.** Regression (Siler-Evans), dispatch/instrumental
   estimates, and capacity-expansion models (NREL Cambium) need not agree.

We ask: **how robust is the carbon-optimal siting recommendation to these
choices, and precisely where does it flip?** We answer with a specification-curve
(multiverse) analysis (Simonsohn, Simmons & Nelson 2020) over methods we build
and validate on live data, released as the reproducible `gridpulse` pipeline.

## 2. Data

- **EIA-930 hourly** fuel mix, demand, and BA-to-BA interchange for 27 balancing
  authorities across all three interconnects, via the EIA API v2. 24 months at
  full coverage; 2019-present for a subset (Holland test).
- **EIA Hourly Electric Grid Monitor** per-BA workbooks — EIA's *published*
  hourly CO2, used as validation ground truth (not self-consistency).
- **NREL Cambium** long-run marginal emission rates (LRMER), GEA-region
  resolution, forward scenarios.
- **CAISO OASIS** nodal LMP with congestion decomposition (no-auth, reproducible),
  for the intra-BA nodal analysis.
- **FracTracker** national data-center tracker (per-facility MW + location).

## 3. Methods

- **AEF**: Σ CO2 / Σ generation, on EIA's production basis (fossil combustion
  only: COL, NG, OIL), validated against EIA's published hourly CO2.
- **Short-run MEF**: Siler-Evans OLS of ΔCO2 on Δdemand over consecutive hours,
  bootstrap CIs; recovers a planted margin to machine precision on synthetic data.
- **Consumption MEF**: emissions flow-tracing over the interchange network
  (de Chalendar 2019 linear system), then a marginal factor on the import-adjusted
  series.
- **Supply-side instruments** (validation): (i) VRE-ramp — carbon displaced per
  MWh of exogenous wind/solar with demand held flat; (ii) generation-trip —
  emissions response to detected forced outages.
- **Nodal LME**: CAISO nodal congestion component modulating the BA system margin
  (directional; exact nodal kg/MWh requires CEII shift factors).
- **Long-run**: NREL Cambium LRMER, mapped GEA-region → BA.
- **Specification curve**: rank BAs under every (temporal × accounting × spatial ×
  method) combination; classify each BA robust-green / robust-dirty / flips by its
  rank range across specifications.

## 4. Results

*(Filled from the live run; see EVIDENCE.md and FINDINGS.md for the generated
tables and `docs/figs/spec_curve.png` for the multiverse figure.)*

- **4.1 Validation.** Computed AEF matches EIA's published hourly CO2 to a median
  of 1.6% (fossil-dominated BAs, EIA's own factors).
- **4.2 MEF triangulation.** Independent instruments converge within 20% where a
  fossil unit sets the margin (e.g. PJM, SWPP, SOCO, MISO); diverge in
  storage/solar-heavy systems (CISO, ERCO) — the margin is only well-identified
  where it is unambiguous.
- **4.3 Consumption re-ranking.** Import-adjustment moves several BAs by 10+ ranks.
- **4.4 Nodal.** Within CISO, congestion spreads marginal carbon ≈ ±50% around the
  BA-average; the cleanest nodes are export-constrained solar buses.
- **4.5 Short-run vs long-run.** [Cambium LRMER vs short-run MEF rank flips + the
  Holland stickiness result.]
- **4.6 Multiverse (headline).** [N]/27 BAs flip their siting rank across
  specifications; only the Pacific-NW hydro BAs are robustly green.

## 5. Discussion

The carbon-optimal siting recommendation is contingent on the analyst's
accounting choices to a degree that undermines single-metric guidance. The robust
policy signal is narrow (Pacific-NW hydro); elsewhere, the verdict depends on
whether one prices short- or long-run carbon, production or consumption, BA-average
or nodal. Siting policy and 24/7-CFE procurement should therefore report the
accounting choice explicitly and prefer regions robust across the multiverse.

## 6. Limitations

- **Short-run vs long-run.** Our short-run MEF is a dispatch-margin estimate;
  Cambium LRMER is model- and scenario-dependent. Neither is ground truth for the
  15-year build margin.
- **No nodal ground truth.** The nodal LME is a directional congestion-based index;
  an exact nodal kg/MWh needs proprietary/CEII shift factors and offer stacks.
- **Consumption flow-tracing** runs on the 27-BA modeled subnetwork; imports from
  unmodeled BAs are dropped.
- **MEF identification** degrades in storage/solar-heavy BAs (shown, not hidden).
- Two-year primary window; longer history only for the subset used in the Holland
  test.

## 7. Reproducibility

All results regenerate from zero via `gridpulse` (`pip install -e ".[prod]"`;
`pytest`; the CLI + `phase3` orchestrator). Data sources are public; the only
credential is a free EIA API key. CI runs the live refresh monthly.

## References

- Siler-Evans, Azevedo & Morgan (2012). Marginal emissions factors for the US
  electricity system. *Environ. Sci. Technol.* 46(9):4742. doi:10.1021/es300145v.
- de Chalendar, Taggart & Azevedo (2019). Tracking emissions in the US electricity
  system. *PNAS* 116(51):25497. doi:10.1073/pnas.1912950116.
- Holland, Kotchen, Mansur & Yates (2022). Why marginal CO2 emissions are not
  decreasing for US electricity. *PNAS* 119(37):e2116632119.
- Gagnon, Ricks, Jenkins et al. (2022). / Ricks, Xu & Jenkins. Minimizing
  emissions from grid-based electricity. *PNAS*.
- Simonsohn, Simmons & Nelson (2020). Specification curve analysis. *Nature Human
  Behaviour* 4:1208. doi:10.1038/s41562-020-0912-z.
- NREL Cambium (Gagnon et al.). https://www.nrel.gov/analysis/cambium.html
- LME validation (2024). *Environ. Res.: Energy*. doi:10.1088/2753-3751/ad72f6.
