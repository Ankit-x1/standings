"""Frozen-fit Monte Carlo final-table simulation and stochastic QA checks."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .data import rebuild_standings
from .models import fit_m1, m1_lambdas
from .probability import outcome_probabilities, skellam_probabilities


@dataclass
class SeasonSimulation:
    teams: list[str]
    points: np.ndarray
    goals_for: np.ndarray
    goals_against: np.ndarray
    average_rank: np.ndarray
    champion_weight: np.ndarray
    top4_weight: np.ndarray
    relegation_weight: np.ndarray
    boundary_date: pd.Timestamp
    training_rows: int
    remaining_rows: int
    seed: int
    draw_counts_remaining: np.ndarray
    points_conservation_ok: bool

    def forecast_table(self, actual_table: pd.DataFrame | None = None) -> pd.DataFrame:
        table = pd.DataFrame({
            "Team": self.teams,
            "ExpectedPts": self.points.mean(axis=0),
            "Pts_p05": np.quantile(self.points, 0.05, axis=0),
            "Pts_p95": np.quantile(self.points, 0.95, axis=0),
            "ExpectedRank": self.average_rank,
            "ChampionProb": self.champion_weight,
            "Top4Prob": self.top4_weight,
            "RelegationProb": self.relegation_weight,
        })
        if actual_table is not None:
            actual = actual_table.set_index("Team")
            table["ActualPts"] = table["Team"].map(actual["Pts"])
            table["ActualRank_display"] = table["Team"].map(actual["Rank"])
            table["ActualPtsIn90Interval"] = (table["ActualPts"] >= table["Pts_p05"]) & (table["ActualPts"] <= table["Pts_p95"])
        return table.sort_values("ExpectedRank", kind="stable").reset_index(drop=True)


def halfway_boundary(matches: pd.DataFrame, target_rows: int = 190) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Split at the first *complete date* whose cumulative row count is >= target."""
    if target_rows < 1:
        raise ValueError("target_rows must be positive")
    ordered = matches.sort_values("Date", kind="stable").reset_index(drop=True)
    cumulative = 0
    boundary: pd.Timestamp | None = None
    for date, batch in ordered.groupby("Date", sort=True):
        cumulative += len(batch)
        if cumulative >= target_rows:
            boundary = pd.Timestamp(date)
            break
    if boundary is None:
        raise ValueError(f"only {len(ordered)} records: cannot reach boundary {target_rows}")
    base = ordered.loc[ordered["Date"] <= boundary].copy().reset_index(drop=True)
    future = ordered.loc[ordered["Date"] > boundary].copy().reset_index(drop=True)
    return base, future, boundary


def _tie_aware_metrics(points: np.ndarray, gf: np.ndarray, ga: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Calculate exact Pts/GD/GF tie ranks and fractional boundary weights.

    Exact equality in all three modeled columns is unresolved (rather than
    applying Premier League head-to-head rules). A tied group crossing a
    boundary shares the available qualifying slots equally.
    """
    simulations, teams = points.shape
    ranks = np.empty((simulations, teams), dtype=float)
    champion = np.zeros((simulations, teams), dtype=float)
    top4 = np.zeros((simulations, teams), dtype=float)
    relegation = np.zeros((simulations, teams), dtype=float)
    gd = gf - ga
    for s in range(simulations):
        # lexsort's final key is primary. A team-id key only gives deterministic
        # iteration order; it never breaks an exact Pts/GD/GF tie substantively.
        order = np.lexsort((np.arange(teams), -gf[s], -gd[s], -points[s]))
        start = 0
        while start < teams:
            end = start + 1
            team = order[start]
            while end < teams and points[s, order[end]] == points[s, team] and gd[s, order[end]] == gd[s, team] and gf[s, order[end]] == gf[s, team]:
                end += 1
            group = order[start:end]
            group_size = end - start
            ranks[s, group] = ((start + 1) + end) / 2.0
            champion[s, group] = max(0, min(end, 1) - start) / group_size
            top4[s, group] = max(0, min(end, 4) - start) / group_size
            relegation[s, group] = max(0, end - max(start, teams - 3)) / group_size
            start = end
    return ranks, champion, top4, relegation


def simulate_remaining_season(
    completed_to_boundary: pd.DataFrame,
    remaining_fixtures: pd.DataFrame,
    simulations: int = 10_000,
    seed: int = 3315,
    shrinkage: float = 0.0,
) -> SeasonSimulation:
    """Freeze Model 1 at the boundary and simulate only listed remaining fixtures.

    Storage is O(simulations × teams), not O(simulations × fixtures × teams).
    """
    if simulations < 1:
        raise ValueError("simulations must be positive")
    teams = sorted(set(completed_to_boundary["HomeTeam"]) | set(completed_to_boundary["AwayTeam"]) | set(remaining_fixtures.get("HomeTeam", [])) | set(remaining_fixtures.get("AwayTeam", [])))
    if not teams:
        raise ValueError("no teams supplied")
    index = {team: i for i, team in enumerate(teams)}
    start_table = rebuild_standings(completed_to_boundary, teams=teams).set_index("Team").reindex(teams)
    nteams = len(teams)
    points = np.repeat(start_table["Pts"].to_numpy(dtype=np.int32)[None, :], simulations, axis=0)
    gf = np.repeat(start_table["GF"].to_numpy(dtype=np.int32)[None, :], simulations, axis=0)
    ga = np.repeat(start_table["GA"].to_numpy(dtype=np.int32)[None, :], simulations, axis=0)
    draw_counts = np.zeros(simulations, dtype=np.int16)
    model = fit_m1(completed_to_boundary, shrinkage=shrinkage)
    rng = np.random.default_rng(seed)
    for fixture in remaining_fixtures.itertuples(index=False):
        h, a = index[fixture.HomeTeam], index[fixture.AwayTeam]
        lh, la = m1_lambdas(model, fixture.HomeTeam, fixture.AwayTeam)
        home_goals = rng.poisson(lh, size=simulations).astype(np.int16)
        away_goals = rng.poisson(la, size=simulations).astype(np.int16)
        gf[:, h] += home_goals
        ga[:, h] += away_goals
        gf[:, a] += away_goals
        ga[:, a] += home_goals
        home_win = home_goals > away_goals
        away_win = away_goals > home_goals
        draw = ~(home_win | away_win)
        points[:, h] += 3 * home_win + draw
        points[:, a] += 3 * away_win + draw
        draw_counts += draw
    ranks, champion, top4, relegation = _tie_aware_metrics(points, gf, ga)
    baseline_points = int(start_table["Pts"].sum())
    expected_total = baseline_points + 3 * len(remaining_fixtures) - draw_counts
    conservation_ok = bool(np.array_equal(points.sum(axis=1), expected_total))
    return SeasonSimulation(
        teams=teams,
        points=points,
        goals_for=gf,
        goals_against=ga,
        average_rank=ranks.mean(axis=0),
        champion_weight=champion.mean(axis=0),
        top4_weight=top4.mean(axis=0),
        relegation_weight=relegation.mean(axis=0),
        boundary_date=pd.Timestamp(completed_to_boundary["Date"].max()),
        training_rows=len(completed_to_boundary),
        remaining_rows=len(remaining_fixtures),
        seed=seed,
        draw_counts_remaining=draw_counts,
        points_conservation_ok=conservation_ok,
    )


def simulate_halfway_season(matches: pd.DataFrame, simulations: int = 10_000, seed: int = 3315, shrinkage: float = 0.0) -> tuple[SeasonSimulation, pd.DataFrame, pd.DataFrame]:
    """Use the first full date at/over 190 records as the frozen fit boundary."""
    base, future, _ = halfway_boundary(matches)
    result = simulate_remaining_season(base, future, simulations, seed, shrinkage)
    return result, base, future


def monte_carlo_qa(lambda_home: float, lambda_away: float, seed: int = 3315, sizes: tuple[int, ...] = (1000, 5000, 10000, 100000)) -> dict:
    """Compare deterministic seeded match simulations with grid/Skellam analytics.

    These are stochastic diagnostics, not guarantees: the standardized
    discrepancies and three-standard-error flag are disclosed in output.
    """
    analytic = outcome_probabilities(lambda_home, lambda_away).probabilities
    skellam = skellam_probabilities(lambda_home, lambda_away)
    rng = np.random.default_rng(seed)
    stability: list[dict] = []
    for n in sizes:
        hg = rng.poisson(lambda_home, n)
        ag = rng.poisson(lambda_away, n)
        observed = np.array([(hg > ag).mean(), (hg == ag).mean(), (hg < ag).mean()])
        se = np.sqrt(analytic * (1 - analytic) / n)
        standardized = np.divide(observed - analytic, se, out=np.zeros(3), where=se > 0)
        stability.append({
            "runs": int(n),
            "frequencies": observed.tolist(),
            "max_abs_standardized_discrepancy": float(np.max(np.abs(standardized))),
            "within_three_standard_errors": bool(np.all(np.abs(standardized) <= 3)),
        })
    # A direct same-seed repetition is a reproducibility check rather than an
    # assertion that different random seeds must agree exactly.
    a = np.random.default_rng(seed).poisson(lambda_home, 128)
    b = np.random.default_rng(seed).poisson(lambda_home, 128)
    return {
        "lambda_home": float(lambda_home),
        "lambda_away": float(lambda_away),
        "analytic_grid": analytic.tolist(),
        "analytic_skellam": skellam.tolist(),
        "grid_skellam_max_abs_difference": float(np.max(np.abs(analytic - skellam))),
        "same_seed_reproducible": bool(np.array_equal(a, b)),
        "stability": stability,
        "interpretation": "Frequency discrepancies are random Monte Carlo error; the 3-SE indicator is a diagnostic, not a deterministic pass promise.",
    }
