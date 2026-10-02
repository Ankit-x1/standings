"""Closed-form independent-Poisson goal models."""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class M0Fit:
    home_mean: float
    away_mean: float


@dataclass(frozen=True)
class M1Fit:
    home_mean: float
    away_mean: float
    home_scored: dict[str, float]
    home_conceded: dict[str, float]
    away_scored: dict[str, float]
    away_conceded: dict[str, float]
    shrinkage: float = 0.0


def fit_m0(training: pd.DataFrame) -> M0Fit:
    """Fit Model 0's league-wide home and away scoring averages."""
    if training.empty:
        raise ValueError("cannot fit a model with no prior completed matches")
    return M0Fit(float(training["FTHG"].mean()), float(training["FTAG"].mean()))


def _rates(training: pd.DataFrame, team_col: str, value_col: str, league_mean: float, shrinkage: float) -> dict[str, float]:
    grouped = training.groupby(team_col)[value_col].agg(["sum", "count"])
    # Explicit optional empirical shrinkage. At zero, observed per-game rates
    # are used exactly; no smoothing is silently applied.
    rate = (grouped["sum"] + shrinkage * league_mean) / (grouped["count"] + shrinkage)
    return {str(team): float(value) for team, value in rate.items()}


def fit_m1(training: pd.DataFrame, shrinkage: float = 0.0) -> M1Fit:
    """Fit Model 1 home-attack/away-defense ratios and their mirror.

    ``shrinkage`` is opt-in pseudo-match weight toward the relevant league
    average. The default is exactly zero, so the classroom formula is used
    unsmoothed. If an entire league side has zero goals, prediction functions
    return the valid degenerate Poisson rate 0 rather than dividing by zero.
    """
    if training.empty:
        raise ValueError("cannot fit a model with no prior completed matches")
    if shrinkage < 0:
        raise ValueError("shrinkage must be nonnegative")
    m0 = fit_m0(training)
    return M1Fit(
        home_mean=m0.home_mean,
        away_mean=m0.away_mean,
        home_scored=_rates(training, "HomeTeam", "FTHG", m0.home_mean, shrinkage),
        home_conceded=_rates(training, "HomeTeam", "FTAG", m0.away_mean, shrinkage),
        away_scored=_rates(training, "AwayTeam", "FTAG", m0.away_mean, shrinkage),
        away_conceded=_rates(training, "AwayTeam", "FTHG", m0.home_mean, shrinkage),
        shrinkage=float(shrinkage),
    )


def _fallback(values: dict[str, float], team: str, fallback: float) -> float:
    return float(values.get(team, fallback))


def m0_lambdas(fit: M0Fit, home: str | None = None, away: str | None = None) -> tuple[float, float]:
    """Return M0 expected goals (team arguments exist for common API symmetry)."""
    return fit.home_mean, fit.away_mean


def m1_lambdas(fit: M1Fit, home: str, away: str) -> tuple[float, float]:
    """Return Model 1 expected goals in the specified home/away orientation."""
    hs = _fallback(fit.home_scored, home, fit.home_mean)
    ac = _fallback(fit.away_conceded, away, fit.home_mean)
    ass = _fallback(fit.away_scored, away, fit.away_mean)
    hc = _fallback(fit.home_conceded, home, fit.away_mean)
    # (HS/mH)*(AC/mH)*mH and its mirror.  If all home/away goals are zero,
    # every relevant rate is zero and the legitimate limiting prediction is 0.
    lam_home = 0.0 if fit.home_mean == 0 else hs * ac / fit.home_mean
    lam_away = 0.0 if fit.away_mean == 0 else ass * hc / fit.away_mean
    return float(lam_home), float(lam_away)
