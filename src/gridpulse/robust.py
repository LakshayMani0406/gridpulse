"""Build 1: robust data-center siting under carbon-accounting-method ambiguity.

The multiverse (Thrust 6) shows the carbon-optimal siting *rank* is fragile: it
flips across defensible accounting methods. This module turns that skeptical
result into a constructive decision rule. Instead of committing to one accounting
method, choose the site that minimises worst-case *regret* across the whole set
of methods -- the min-max-regret site.

Ambiguity set M = the marginal carbon-accounting methods gridpulse already
computes (the multiverse spec columns, excluding the average factor AEF): the
short-run Siler-Evans MEF, the VRE-instrument MEF, the consumption (flow-traced)
MEF, the Cambium long-run LRMER, the Cambium SRMER, and -- once Build 2 lands --
the state-dependent autoregressive MEF. Each method m assigns a carbon cost
c_m(r) (kg CO2 / MWh) to a fixed candidate load in region r. From the committed
factor matrix (``data/multiverse_factors.csv``):

    regret(r, m)      = c_m(r) - min_r' c_m(r')            absolute   (kg/MWh)
    rel_regret(r, m)  = regret(r, m) / min_r' c_m(r')      relative   (guarded)
    norm_regret(r, m) = regret(r, m) / (max_r' - min_r')   scale-free ([0, 1])
    robust site  r*   = argmin_r  max_m  regret(r, m)      min-max regret

Reporting: the region x method regret matrix; r*; the *price of robustness*
(regret of r* under each individual method = how much worse r* is than that
method's own optimum); and the *low-regret core* (regions within eps of optimal
across ALL methods). An OWA / weighted-scenario aggregation interpolates between
min-max (all weight on the worst method) and average regret.

Absolute regret is dominated by the highest-level method, so the min-max site is
reported on both the absolute and the scale-free normalised regret; they agree
here (both select the Pacific-NW hydro core), which is the robustness claim.

Refs. Min-max / min-max regret over a discrete scenario set: Aissi, Bazgan &
Vanderpooten (2009), Eur. J. Oper. Res. 197(2):427-438,
doi:10.1016/j.ejor.2008.09.012; Bertsimas & Sim (2004), Oper. Res. 52(1):35-53,
doi:10.1287/opre.1030.0065; Ben-Tal, El Ghaoui & Nemirovski (2009), Robust
Optimization, Princeton. Precedent for min-max regret across competing *models*
(transplanted here to competing accounting *methods*): Rezai & van der Ploeg
(2017), "Climate policies under climate model uncertainty: max-min and min-max
regret," Energy Economics 68:4-16, doi:10.1016/j.eneco.2017.10.018. OWA:
Yager (1988), IEEE Trans. Syst. Man Cybern. 18(1):183-190,
doi:10.1109/21.87068.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

AEF_COL = "AEF (avg, prod, BA)"
# The three regret conventions supported by this module.
KINDS = ("absolute", "relative", "normalized")


def load_factor_matrix(
    path: str | Path = "data/multiverse_factors.csv",
    methods: list[str] | None = None,
    include_aef: bool = False,
) -> pd.DataFrame:
    """Load the committed region x method carbon-cost matrix c_m(r) (kg/MWh).

    ``data/multiverse_factors.csv`` is the exact factor matrix underlying the
    committed multiverse ranks (verified: ranking it reproduces
    ``multiverse_ranks.csv``). By default the ambiguity set is the *marginal*
    methods -- the average factor (AEF) is excluded because the paper's thesis is
    that the average is the wrong signal for a marginal load; pass
    ``include_aef=True`` for the sensitivity. ``methods`` overrides the column
    selection explicitly.
    """
    df = pd.read_csv(path).set_index("ba")
    if methods is not None:
        return df[methods]
    if not include_aef:
        df = df[[c for c in df.columns if c != AEF_COL]]
    return df


# --------------------------------------------------------------- regret matrices
def regret_matrix(factors: pd.DataFrame, kind: str = "absolute") -> pd.DataFrame:
    """Region x method regret under one convention. Lower cost = better; the
    method optimum has zero regret. NaN cost (a method that yields no estimate
    for a BA) stays NaN and is skipped by the min-max aggregation.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    out = {}
    for m in factors.columns:
        col = factors[m]
        lo = col.min(skipna=True)
        hi = col.max(skipna=True)
        gap = col - lo
        if kind == "absolute":
            out[m] = gap
        elif kind == "relative":
            # relative to the method optimum; undefined when the optimum is <= 0
            # (e.g. consumption MEF floored at 0 for CISO) -> NaN, reported as such
            out[m] = gap / lo if lo > 0 else pd.Series(np.nan, index=col.index)
        else:  # normalized: fraction of the method's own spread, scale-free in [0,1]
            rng = hi - lo
            out[m] = gap / rng if rng > 0 else pd.Series(0.0, index=col.index)
    return pd.DataFrame(out)[list(factors.columns)]


def min_max_regret(factors: pd.DataFrame, kind: str = "absolute") -> pd.DataFrame:
    """Per-region worst-case regret and the binding (worst) method, ascending.

    The first row is the min-max-regret site r*. ``n_methods`` flags coverage
    (a BA missing a method is scored on the methods it has).
    """
    reg = regret_matrix(factors, kind=kind)
    tbl = pd.DataFrame({
        "max_regret": reg.max(axis=1, skipna=True),
        "worst_method": reg.idxmax(axis=1),
        "mean_regret": reg.mean(axis=1, skipna=True),
        "n_methods": reg.notna().sum(axis=1),
    })
    return tbl.sort_values("max_regret")


def robust_site(factors: pd.DataFrame, kind: str = "absolute") -> str:
    """The min-max-regret site r* = argmin_r max_m regret(r, m)."""
    return str(min_max_regret(factors, kind=kind).index[0])


def price_of_robustness(factors: pd.DataFrame, site: str, kind: str = "absolute") -> pd.Series:
    """Regret of ``site`` under each method: how much worse it is than that
    method's own optimum. The price a developer pays for insuring against the
    accounting choice, method by method.
    """
    return regret_matrix(factors, kind=kind).loc[site].sort_values(ascending=False)


def low_regret_core(factors: pd.DataFrame, eps: float = 0.10, kind: str = "normalized") -> list[str]:
    """Regions within ``eps`` of optimal across EVERY method (max_m regret <= eps).

    On the normalised convention eps is a fraction of each method's spread; the
    default eps=0.10 means "never more than 10% of the way from best to worst on
    any accounting method." NaN (missing method) is treated as failing the bound
    only if the BA has no estimate for that method AND we require full coverage;
    here we require the bound to hold on all methods the BA actually has.
    """
    reg = regret_matrix(factors, kind=kind)
    worst = reg.max(axis=1, skipna=True)
    core = worst[worst <= eps].sort_values()
    return core.index.tolist()


# --------------------------------------------------------------- OWA aggregation
def owa_regret(
    factors: pd.DataFrame,
    weights: np.ndarray | list[float] | str | None = None,
    kind: str = "absolute",
) -> pd.DataFrame:
    """Ordered-weighted-average regret per region, ascending (best first).

    The regret vector of each region is sorted worst-first and dotted with
    ``weights``. ``weights`` may be an explicit vector, or one of:
      "minmax"  -> all weight on the worst method (recovers min-max regret),
      "average" -> equal weight (Hurwicz-style mean regret; the default),
      "linear"  -> linearly decreasing weights (a middle ground).
    Equal weights are the default because no method in the ambiguity set is
    a priori more credible than another (fork (b): no weighting could be
    inferred, so all accounting methods are weighted equally).
    """
    reg = regret_matrix(factors, kind=kind)
    k = reg.shape[1]
    if weights is None or (isinstance(weights, str) and weights == "average"):
        w = np.full(k, 1.0 / k)
    elif isinstance(weights, str) and weights == "minmax":
        w = np.zeros(k)
        w[0] = 1.0
    elif isinstance(weights, str) and weights == "linear":
        w = np.arange(k, 0, -1, dtype=float)
        w /= w.sum()
    else:
        w = np.asarray(weights, dtype=float)
        w = w / w.sum()

    def _owa(row: pd.Series) -> float:
        v = np.sort(row.dropna().to_numpy())[::-1]  # worst first
        ww = w[: len(v)]
        ww = ww / ww.sum() if ww.sum() else ww      # renormalise if BA misses a method
        return float(np.dot(v, ww))

    score = reg.apply(_owa, axis=1)
    return pd.DataFrame({"owa_regret": score}).sort_values("owa_regret")


# --------------------------------------------------------------- hedge extension
def hedge_pairs(
    factors: pd.DataFrame,
    top: int = 10,
    candidates: list[str] | None = None,
) -> pd.DataFrame:
    """Min-max-regret two-region hedges in absolute kg/MWh (paper's Rule B).

    A load splittable across a pair {r1, r2} can take the better of the two under
    each method, so the pair cost under method m is min(c_m(r1), c_m(r2)). The
    pair's worst-case regret is max_m [ min(c_m(r1), c_m(r2)) - min_r' c_m(r') ],
    always benchmarked against the *global* per-method optimum. We also report
    each pair's rank-vector correlation across methods: strongly anti-correlated
    pairs hedge the accounting choice, which is why they can beat either site
    alone. ``candidates`` restricts which regions may form pairs (e.g. exclude
    the robust core to formalise "hedge when the hydro core is unavailable"),
    while the regret benchmark stays the global optimum. Returns the ``top``
    pairs by lowest worst-case regret.
    """
    cols = list(factors.columns)
    optima = factors.min(axis=0, skipna=True)[cols].to_numpy(dtype=float)
    ranks = factors.rank(axis=0, method="min")  # for the anti-correlation diagnostic
    pool = list(candidates) if candidates is not None else list(factors.index)
    rows = []
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            a, b = pool[i], pool[j]
            pair_cost = np.minimum(factors.loc[a, cols].to_numpy(dtype=float),
                                   factors.loc[b, cols].to_numpy(dtype=float))
            max_reg = float(np.nanmax(pair_cost - optima))
            ra, rb = ranks.loc[a], ranks.loc[b]
            common = ra.dropna().index.intersection(rb.dropna().index)
            if len(common) >= 3 and ra[common].std() > 0 and rb[common].std() > 0:
                corr = float(ra[common].corr(rb[common]))
            else:
                corr = np.nan
            rows.append({"ba_a": a, "ba_b": b, "pair_max_regret": max_reg,
                         "rank_corr": corr})
    out = pd.DataFrame(rows).sort_values("pair_max_regret").reset_index(drop=True)
    return out.head(top)


# --------------------------------------------------------------- summary
def summarize(factors: pd.DataFrame, eps: float = 0.10) -> dict:
    """One-call summary for FINDINGS: r* (absolute and normalized), its price of
    robustness, the low-regret core, and the single best hedge pair.
    """
    r_abs = robust_site(factors, "absolute")
    r_norm = robust_site(factors, "normalized")
    mmr = min_max_regret(factors, "absolute")
    hedge = hedge_pairs(factors, top=1)
    return {
        "n_methods": int(factors.shape[1]),
        "methods": list(factors.columns),
        "n_regions": int(factors.shape[0]),
        "robust_site_absolute": r_abs,
        "robust_site_normalized": r_norm,
        "robust_site_max_regret_kgmwh": float(mmr.loc[r_abs, "max_regret"]),
        "robust_site_binding_method": str(mmr.loc[r_abs, "worst_method"]),
        "price_of_robustness_kgmwh": price_of_robustness(factors, r_abs, "absolute").to_dict(),
        "low_regret_core": low_regret_core(factors, eps=eps, kind="normalized"),
        "low_regret_eps": eps,
        "runner_up": str(mmr.index[1]),
        "runner_up_max_regret_kgmwh": float(mmr.iloc[1]["max_regret"]),
        "best_hedge": hedge.iloc[0].to_dict() if not hedge.empty else {},
    }


# --------------------------------------------------------- estimation uncertainty
# The 10x: the min-max is over BOTH the accounting method AND the estimation
# uncertainty of the short-run regression MEF. We draw the regression MEF per BA
# (bootstrap or reference-prior Bayesian), then either (a) recompute the min-max
# site per draw to see how often the robust site survives, or (b) fold every draw
# in as its own scenario for a single distributionally-robust site.
def mef_estimation_draws(
    assembled: pd.DataFrame,
    driver: str = "demand",
    n_draws: int = 500,
    method: str = "bootstrap",
    seed: int = 42,
) -> pd.DataFrame:
    """Per-BA draws of the short-run regression MEF (estimation uncertainty).

    Returns DataFrame [draw x BA]. ``method="bootstrap"`` case-resamples the
    ΔCO2~Δdriver pairs; ``method="bayesian"`` samples the reference-prior
    (Jeffreys) posterior of the OLS slope, Student-t(df=n-2) at the estimate with
    its analytic standard error. Each BA uses an independent random stream.
    """
    from . import emissions
    cols: dict[str, np.ndarray] = {}
    for i, (ba, grp) in enumerate(assembled.groupby("ba")):
        x, y = emissions.mef_pairs(grp, driver=driver)
        if len(x) < 3:
            continue
        if method == "bootstrap":
            cols[str(ba)] = emissions.bootstrap_slopes(x, y, n_boot=n_draws, seed=seed + i)
        elif method == "bayesian":
            slope, se, n = emissions.ols_slope_se(x, y)
            if not np.isfinite(se) or n <= 2:
                cols[str(ba)] = np.full(n_draws, slope)
            else:
                rng = np.random.default_rng(seed + i)
                cols[str(ba)] = slope + se * rng.standard_t(n - 2, size=n_draws)
        else:
            raise ValueError("method must be 'bootstrap' or 'bayesian'")
    return pd.DataFrame(cols)


def robust_site_under_uncertainty(
    factors: pd.DataFrame,
    mef_draws: pd.DataFrame,
    regression_col: str = "MEF short-run prod (regression)",
    kind: str = "absolute",
    eps: float = 0.10,
) -> dict:
    """Distribution of the min-max-regret site when the regression MEF column is
    replaced by each estimation draw. Reports how often the point robust site and
    the low-regret core survive the estimation uncertainty."""
    if regression_col not in factors.columns:
        raise ValueError(regression_col)
    common = [b for b in factors.index if b in mef_draws.columns]
    sub = factors.loc[common].copy()
    point_site = robust_site(sub, kind)
    core_ref = set(low_regret_core(sub, eps, "normalized"))
    sites: list[str] = []
    core_hits = 0
    base = sub.copy()
    for row in mef_draws[common].to_numpy(dtype=float):
        base[regression_col] = row
        sites.append(robust_site(base, kind))
        if set(low_regret_core(base, eps, "normalized")) == core_ref:
            core_hits += 1
    n = len(sites)
    probs = pd.Series(sites).value_counts(normalize=True)
    return {
        "n_draws": n,
        "point_site": point_site,
        "p_point_site_is_robust": float(probs.get(point_site, 0.0)),
        "site_probs": probs.round(4).to_dict(),
        "core_ref": sorted(core_ref),
        "p_core_stable": core_hits / n if n else float("nan"),
    }


def distributionally_robust_site(
    factors: pd.DataFrame,
    mef_draws: pd.DataFrame,
    regression_col: str = "MEF short-run prod (regression)",
    kind: str = "absolute",
) -> dict:
    """Single min-max-regret site over the joint scenario set = the non-regression
    methods PLUS every estimation draw of the regression MEF (method choice and
    estimation uncertainty as one ambiguity set)."""
    common = [b for b in factors.index if b in mef_draws.columns]
    base = factors.loc[common].drop(columns=[regression_col])
    draws_t = mef_draws[common].T
    draws_t.columns = [f"{regression_col} ~draw{i}" for i in range(draws_t.shape[1])]
    aug = pd.concat([base, draws_t], axis=1)
    mmr = min_max_regret(aug, kind=kind)
    return {"dr_site": str(mmr.index[0]),
            "dr_max_regret": float(mmr.iloc[0]["max_regret"]),
            "runner_up": str(mmr.index[1]),
            "n_scenarios": int(aug.shape[1])}
