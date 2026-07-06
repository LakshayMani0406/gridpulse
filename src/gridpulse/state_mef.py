"""Build 2 (Thrust 7): state-dependent autoregressive marginal emission factor.

gridpulse's short-run MEF is a single Siler-Evans slope per BA; the three-way
supply-side triangulation (Thrust 3) converges within 20% for only 6/23 BAs.
This adds a fourth, more principled estimator whose marginal factor is
*state-dependent* -- a latent regime switches the whole parameter vector -- with
an *autoregressive* component, since the marginal unit persists hour-to-hour via
unit commitment.

Specification: a two-regime Markov-switching model with autoregressive and
exogenous terms, MS-ARX(1), per BA (Panico, Burlinson & Grossi 2026,
arXiv:2603.04260, their Eq. 5):

    y_t = alpha_{S_t} + phi_{S_t} y_{t-1} + b1_{S_t} x1_t + b2_{S_t} x2_t + eps_t

with y_t = hourly CO2, x1_t = non-renewable generation, x2_t = renewable
generation, S_t a latent 2-state Markov chain (estimated by the Hamilton filter +
EM), and variance common across regimes. b1_{S_t} is the regime-specific MEF. We
report both regime MEFs, the ergodic-probability-weighted scalar MEF (used for
triangulation and the robust-siting ambiguity set), and per-regime standard
errors. Following the paper we drive off actual hourly *generation* (not load),
so imported carbon is not misattributed to local marginal units -- gridpulse
already computes CO2 from generation (``emissions.hourly_co2``).

The states are latent, not imposed; the paper validates them ex post as a
gas-driven low-MEF regime and a coal-driven high-MEF regime. When a BA's two
regime MEFs are far apart, its marginal factor is genuinely regime-dependent --
which is a first-principles explanation for why single-slope estimators diverge
there.

Predecessor AR-MEF method: Beltrami, Burlinson, Giulietti, Grossi, Rowley &
Wilson (2020), "Where did the time (series) go? Estimation of marginal emission
factors with autoregressive components," Energy Economics 91:104905,
doi:10.1016/j.eneco.2020.104905.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .causal_mef import _wide
from .config import HAS_STATSMODELS

log = logging.getLogger("gridpulse.state_mef")

# Renewable generation for the x2 regressor; non-renewable = total gen - renewable.
RENEWABLE_FUELS = ("WAT", "SUN", "WND", "GEO")
# exog order fed to the model: [y_{t-1}, non-renewable gen, renewable gen].
# statsmodels labels exog positionally x1, x2, ...; the MEF is the 2nd exog.
_MEF_LABEL = "x2"
_PHI_LABEL = "x1"


def _model_frame(w: pd.DataFrame) -> pd.DataFrame | None:
    """Per-hour modelling frame from causal_mef._wide: y=co2 (t), y_{t-1}, and
    non-renewable / renewable generation, restricted to consecutive hours so the
    lag is the true previous clock hour. Values scaled (CO2->tonnes, gen->GWh) for
    numerical conditioning; the MEF coefficient is invariant to this (kg/MWh)."""
    if w.empty or "co2_kg" not in w or "gen_mwh" not in w:
        return None
    d = w.sort_values("period").reset_index(drop=True).copy()
    ren_cols = [c for c in RENEWABLE_FUELS if c in d.columns]
    d["renew"] = d[ren_cols].sum(axis=1) if ren_cols else 0.0
    d["nonrenew"] = (d["gen_mwh"] - d["renew"]).clip(lower=0)
    d["ylag"] = d["co2_kg"].shift(1)
    consec = pd.to_datetime(d["period"]).diff() == pd.Timedelta(hours=1)
    d = d[consec].dropna(subset=["co2_kg", "ylag", "nonrenew", "renew"])
    out = pd.DataFrame({
        "y": d["co2_kg"].to_numpy() / 1000.0,          # tonnes
        "ylag": d["ylag"].to_numpy() / 1000.0,
        "nonrenew": d["nonrenew"].to_numpy() / 1000.0,  # GWh
        "renew": d["renew"].to_numpy() / 1000.0,
    })
    return out


def _ergodic(P: np.ndarray) -> np.ndarray:
    """Stationary distribution of a column-stochastic transition matrix P
    (statsmodels convention P[i,j] = P(S_t=i | S_{t-1}=j))."""
    evals, evecs = np.linalg.eig(P)
    pi = np.real(evecs[:, int(np.argmin(np.abs(evals - 1.0)))])
    pi = np.abs(pi)
    s = pi.sum()
    return pi / s if s else np.full(len(pi), 1.0 / len(pi))


def state_ar_mef(
    w: pd.DataFrame,
    k_regimes: int = 2,
    search_reps: int = 10,
    min_obs: int = 500,
    seed: int = 42,
) -> dict | None:
    """Fit MS-ARX(1) for one BA (per-hour frame ``w`` from causal_mef._wide).

    Returns the ergodic-weighted MEF, both regime MEFs with standard errors,
    regime weights, AR coefficients, and the regime spread; or None if
    statsmodels is absent, the data is insufficient, or the fit fails.
    """
    if not HAS_STATSMODELS:
        return None
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

    f = _model_frame(w)
    ba = str(w["ba"].iloc[0]) if "ba" in w.columns and len(w) else "?"
    if f is None or len(f) < min_obs or f["nonrenew"].std() == 0:
        return None
    np.random.seed(seed)
    try:
        mod = MarkovRegression(f["y"], k_regimes=k_regimes, trend="c",
                               exog=f[["ylag", "nonrenew", "renew"]],
                               switching_variance=False)
        res = mod.fit(search_reps=search_reps, maxiter=200, disp=False)
    except Exception as e:  # non-convergence, singular matrices, etc.
        log.warning("MS-ARX failed for %s: %s", ba, str(e)[:70])
        return None

    reg = range(k_regimes)
    try:
        mef = {i: float(res.params[f"{_MEF_LABEL}[{i}]"]) for i in reg}
        phi = {i: float(res.params[f"{_PHI_LABEL}[{i}]"]) for i in reg}
    except KeyError as e:
        log.warning("MS-ARX param labels unexpected for %s: %s", ba, e)
        return None
    try:
        se = {i: float(res.bse[f"{_MEF_LABEL}[{i}]"]) for i in reg}
    except Exception:
        se = {i: float("nan") for i in reg}

    pi = _ergodic(res.regime_transition[:, :, 0])
    pi = {i: float(pi[i]) for i in reg}
    mef_erg = float(sum(pi[i] * mef[i] for i in reg))
    lo = min(reg, key=lambda i: mef[i])
    hi = max(reg, key=lambda i: mef[i])
    return {
        "mef_state_ar": mef_erg,
        "mef_low_regime": mef[lo], "mef_high_regime": mef[hi],
        "se_low_regime": se[lo], "se_high_regime": se[hi],
        "pi_low": pi[lo], "pi_high": pi[hi],
        "phi_low": phi[lo], "phi_high": phi[hi],
        "regime_spread_pct": float(100 * (mef[hi] - mef[lo]) / mef_erg) if mef_erg else np.nan,
        "n_obs": int(len(f)), "llf": float(res.llf),
    }


def state_ar_mef_by_ba(fuel_long: pd.DataFrame, demand_long: pd.DataFrame,
                       bas: list[str], **kw) -> pd.DataFrame:
    """Per-BA MS-ARX(1) MEF table. BAs that fail to fit are omitted."""
    rows = []
    for ba in bas:
        w = _wide(fuel_long, demand_long, ba)
        if not w.empty:
            w["ba"] = ba  # so failures log the real BA (the pivot drops it)
        r = state_ar_mef(w, **kw)
        if r is None:
            continue
        r["ba"] = ba
        rows.append(r)
    cols = ["ba", "mef_state_ar", "mef_low_regime", "mef_high_regime",
            "se_low_regime", "se_high_regime", "pi_low", "pi_high",
            "phi_low", "phi_high", "regime_spread_pct", "n_obs", "llf"]
    return pd.DataFrame(rows, columns=cols)


def convergence_count(df: pd.DataFrame, cols: list[str], tol_pct: float = 20.0,
                      min_estimates: int = 2) -> tuple[int, int]:
    """Count BAs whose available estimates in ``cols`` agree within ``tol_pct``
    (range / mean). Returns (n_converge, n_evaluable)."""
    conv = evald = 0
    for _, r in df.iterrows():
        vals = np.array([r[c] for c in cols if c in r and pd.notna(r[c])], float)
        if len(vals) < min_estimates:
            continue
        evald += 1
        mean = vals.mean()
        if mean and 100 * (vals.max() - vals.min()) / abs(mean) <= tol_pct:
            conv += 1
    return conv, evald
