"""Exploratory diagnostics used in the generated report."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import poisson


def calibration_table(predictions: pd.DataFrame, model: str = "M1", bins: int = 10) -> pd.DataFrame:
    """Ternary calibration table: every H/D/A event probability is one datum."""
    probs = predictions[[f"{model}_H", f"{model}_D", f"{model}_A"]].to_numpy(float).ravel()
    actual_lookup = {"H": 0, "D": 1, "A": 2}
    actual = np.zeros((len(predictions), 3), dtype=float)
    actual[np.arange(len(predictions)), predictions["FTR"].map(actual_lookup).to_numpy()] = 1.0
    observed = actual.ravel()
    edges = np.linspace(0, 1, bins + 1)
    # Include exact 1.0 in the final bin.
    category = np.minimum(np.digitize(probs, edges, right=False) - 1, bins - 1)
    records = []
    for b in range(bins):
        mask = category == b
        if mask.any():
            records.append({"bin": b, "lower": edges[b], "upper": edges[b + 1], "count": int(mask.sum()), "mean_predicted": float(probs[mask].mean()), "observed_frequency": float(observed[mask].mean())})
    return pd.DataFrame(records)


def _make_bins(goals: np.ndarray, lambda_hat: float) -> list[tuple[int, int | None]]:
    # Include a tail bin past an essentially complete Poisson support.
    kmax = max(int(goals.max(initial=0)), int(math.ceil(poisson.ppf(1 - 1e-10, lambda_hat))))
    bins: list[tuple[int, int | None]] = [(k, k) for k in range(kmax + 1)] + [(kmax + 1, None)]
    return bins


def _expected_probability(low: int, high: int | None, lam: float) -> float:
    if high is None:
        return float(poisson.sf(low - 1, lam))
    return float(poisson.cdf(high, lam) - poisson.cdf(low - 1, lam))


def _counts(goals: np.ndarray, bins: list[tuple[int, int | None]]) -> np.ndarray:
    return np.array([np.sum(goals >= lo) if hi is None else np.sum((goals >= lo) & (goals <= hi)) for lo, hi in bins], dtype=float)


def pooled_poisson_gof(matches: pd.DataFrame, replicates: int = 1000, seed: int = 3315) -> tuple[pd.DataFrame, dict]:
    """Exploratory Pearson GOF with sparse bins pooled and λ refit in bootstrap.

    The reported bootstrap p-value is preferable to a naïve chi-square p-value
    because λ is estimated and sparse categories are pooled. It remains an
    exploratory whole-league diagnostic, not evidence that teams are iid.
    """
    if replicates < 1:
        raise ValueError("replicates must be positive")
    goals = np.r_[matches["FTHG"].to_numpy(int), matches["FTAG"].to_numpy(int)]
    if len(goals) == 0:
        raise ValueError("no goals for diagnostic")
    lam = float(goals.mean())
    bins = _make_bins(goals, lam)
    observed = _counts(goals, bins)
    expected = np.array([len(goals) * _expected_probability(lo, hi, lam) for lo, hi in bins])
    # Pool sparse categories from the upper tail inward. This preserves
    # adjacent bins and makes the final categories auditable.
    pooled: list[list[float | int | None]] = [[lo, hi, o, e] for (lo, hi), o, e in zip(bins, observed, expected)]
    i = len(pooled) - 1
    while i > 0:
        if float(pooled[i][3]) < 5:
            previous = pooled[i - 1]
            previous[1] = pooled[i][1]
            previous[2] = float(previous[2]) + float(pooled[i][2])
            previous[3] = float(previous[3]) + float(pooled[i][3])
            pooled.pop(i)
        i -= 1
    obs = np.array([float(item[2]) for item in pooled])
    exp = np.array([float(item[3]) for item in pooled])
    statistic = float(np.sum((obs - exp) ** 2 / exp))
    rng = np.random.default_rng(seed)
    boot = np.empty(replicates, dtype=float)
    pooled_bins = [(int(item[0]), None if item[1] is None else int(item[1])) for item in pooled]
    for b in range(replicates):
        sample = rng.poisson(lam, len(goals))
        refit = float(sample.mean())
        boot_obs = _counts(sample, pooled_bins)
        boot_exp = np.array([len(sample) * _expected_probability(lo, hi, refit) for lo, hi in pooled_bins])
        boot[b] = np.sum((boot_obs - boot_exp) ** 2 / boot_exp)
    labels = [f"{lo}+" if hi is None else (str(lo) if lo == hi else f"{lo}-{hi}") for lo, hi in pooled_bins]
    table = pd.DataFrame({"Goals": labels, "Observed": obs.astype(int), "ExpectedPoisson": exp})
    result = {
        "n_team_match_goal_counts": int(len(goals)),
        "lambda_hat": lam,
        "pearson_statistic": statistic,
        "pooled_bins": labels,
        "all_expected_at_least_5": bool((exp >= 5).all()),
        "parametric_bootstrap_p_value": float((1 + np.sum(boot >= statistic)) / (replicates + 1)),
        "bootstrap_replicates": int(replicates),
        "seed": int(seed),
        "limitation": "Exploratory pooled league-wide diagnostic; it refits lambda in each parametric bootstrap sample and does not establish independent identical team scoring.",
    }
    return table, result
