"""Exact independent-Poisson score and outcome probabilities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import numpy as np
from scipy.stats import poisson, skellam


@dataclass(frozen=True)
class OutcomeGrid:
    home: float
    draw: float
    away: float
    tail_mass: float
    raw_mass: float
    max_goals: int
    matrix: np.ndarray

    @property
    def probabilities(self) -> np.ndarray:
        return np.array([self.home, self.draw, self.away], dtype=float)

    def to_dict(self) -> dict:
        result = asdict(self)
        result.pop("matrix")
        result["probabilities"] = {"H": self.home, "D": self.draw, "A": self.away}
        return result


def _check_lambda(value: float, label: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return value


def score_matrix(lambda_home: float, lambda_away: float, tolerance: float = 1e-8, start_max_goals: int = 10) -> OutcomeGrid:
    """Build a normalized adaptive score grid, beginning with scores 0..10.

    The unrepresented joint tail is recorded before normalisation. The cap is
    expanded in blocks of five until that tail is below ``tolerance``.
    """
    lh = _check_lambda(lambda_home, "lambda_home")
    la = _check_lambda(lambda_away, "lambda_away")
    if not 0 < tolerance < 1:
        raise ValueError("tolerance must be between zero and one")
    max_goals = max(10, int(start_max_goals))
    while True:
        joint_mass = float(poisson.cdf(max_goals, lh) * poisson.cdf(max_goals, la))
        tail = max(0.0, 1.0 - joint_mass)
        if tail < tolerance:
            break
        max_goals += 5
        if max_goals > 10000:  # defensive protection for invalid use
            raise RuntimeError("adaptive score grid did not converge")
    goals = np.arange(max_goals + 1)
    matrix = np.outer(poisson.pmf(goals, lh), poisson.pmf(goals, la))
    raw_mass = float(matrix.sum())
    matrix /= raw_mass
    home = float(np.tril(matrix, k=-1).sum())
    draw = float(np.trace(matrix))
    away = float(np.triu(matrix, k=1).sum())
    return OutcomeGrid(home, draw, away, tail, raw_mass, max_goals, matrix)


def outcome_probabilities(lambda_home: float, lambda_away: float, **kwargs: object) -> OutcomeGrid:
    """Alias for the adaptive-grid home/draw/away probabilities."""
    return score_matrix(lambda_home, lambda_away, **kwargs)


def skellam_probabilities(lambda_home: float, lambda_away: float) -> np.ndarray:
    """Return exact H/D/A probabilities from the Skellam goal-difference law.

    SciPy's Skellam is undefined at zero rates, so all degenerate zero-rate
    cases are handled explicitly.
    """
    lh = _check_lambda(lambda_home, "lambda_home")
    la = _check_lambda(lambda_away, "lambda_away")
    if lh == 0 and la == 0:
        return np.array([0.0, 1.0, 0.0])
    if lh == 0:
        draw = math.exp(-la)
        return np.array([0.0, draw, 1.0 - draw])
    if la == 0:
        draw = math.exp(-lh)
        return np.array([1.0 - draw, draw, 0.0])
    return np.array([float(skellam.sf(0, lh, la)), float(skellam.pmf(0, lh, la)), float(skellam.cdf(-1, lh, la))])
