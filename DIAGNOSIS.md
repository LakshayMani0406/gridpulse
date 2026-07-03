# DIAGNOSIS — what problem gridpulse solves

**The mistake in the literature.** Studies that rank regions for data-center
siting (e.g. Jha et al., *Frontiers* 2024) use **average** grid emission factors
(AEF): total CO2 ÷ total generation. But a new data center does not consume the
average MWh — it *adds* load, met by whatever unit is on the **margin**, which in
most US balancing authorities is fossil (gas or coal). The relevant number is the
**marginal** emission factor (MEF).

**Why it matters.** AEF and MEF can *invert* the ranking of "greenest" regions. A
hydro- or nuclear-rich balancing authority looks clean on average, but its extra
MWh comes from a gas peaker — so siting new load there can be *worse* than a region
with a higher average but a cleaner margin. Optimizing on the wrong metric sends
gigawatts of new load to the wrong place.

**The second-order mistake.** Even MEF, computed production-side, ignores trade: a
BA that imports dirty power should be charged for those imports. The siting-correct
number is the **consumption-based** (import-adjusted) marginal factor, which
requires tracing interchange flows across the BA network.

**What gridpulse does about it.**
1. Computes AEF and Siler-Evans MEF per BA from live EIA hourly data.
2. Validates the AEF against EIA's own published hourly CO2 (real ground truth).
3. Traces interchange flows for consumption-based marginal carbon.
4. Quantifies the gap between the actual data-center build-out and a
   carbon-optimal one.

See `RESEARCH.md` for methods/citations and `PLAN.md` for the build.
