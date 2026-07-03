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

