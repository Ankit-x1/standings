"""Unit tests use synthetic fixtures only; no synthetic data enter the analysis."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from standings.data import DataValidationError, load_matches, rebuild_standings
from standings.diagnostics import calibration_table, pooled_poisson_gof
from standings.evaluation import brier_losses, date_block_bootstrap, market_probabilities, one_hot, rps_losses, walk_forward
from standings.models import fit_m0, fit_m1, m1_lambdas
from standings.probability import outcome_probabilities, skellam_probabilities
from standings.simulation import halfway_boundary, monte_carlo_qa, simulate_remaining_season


def row(day: str, home: str, away: str, hg: int, ag: int, **extra: object) -> dict:
    return {"Date": pd.Timestamp(day), "HomeTeam": home, "AwayTeam": away, "FTHG": hg, "FTAG": ag, "FTR": "H" if hg > ag else "A" if hg < ag else "D", "AvgCH": "2.0", "AvgCD": "3.2", "AvgCA": "4.0", **extra}


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def write_results(path: Path, rows: list[dict]) -> None:
    fields = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "AvgCH", "AvgCD", "AvgCA"]
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})


def test_grid_normalizes_and_records_small_tail() -> None:
    grid = outcome_probabilities(1.4, 1.1)
    assert np.isclose(grid.probabilities.sum(), 1)
    assert grid.tail_mass < 1e-8
    assert grid.max_goals >= 10


def test_adaptive_grid_grows_beyond_initial_cap() -> None:
    grid = outcome_probabilities(20, 18)
    assert grid.max_goals > 10
    assert grid.tail_mass < 1e-8


def test_skellam_matches_adaptive_grid() -> None:
    grid = outcome_probabilities(1.8, 0.7)
    assert np.allclose(grid.probabilities, skellam_probabilities(1.8, 0.7), atol=1e-8)


def test_skellam_handles_double_zero_lambda() -> None:
    assert np.array_equal(skellam_probabilities(0, 0), [0, 1, 0])


def test_skellam_handles_one_zero_lambda() -> None:
    p = skellam_probabilities(0, 2)
    assert p[0] == 0 and np.isclose(p[1], np.exp(-2)) and np.isclose(p.sum(), 1)


def test_m1_has_correct_home_away_orientation() -> None:
    training = frame([
        row("2025-01-01", "H", "A", 4, 1),
        row("2025-01-02", "H", "B", 2, 2),
        row("2025-01-03", "C", "A", 1, 3),
        row("2025-01-04", "C", "B", 0, 1),
    ])
    fit = fit_m1(training)
    lh, la = m1_lambdas(fit, "H", "A")
    assert np.isclose(lh, fit.home_scored["H"] * fit.away_conceded["A"] / fit.home_mean)
    assert np.isclose(la, fit.away_scored["A"] * fit.home_conceded["H"] / fit.away_mean)


def test_zero_goal_league_returns_zero_lambdas() -> None:
    training = frame([row("2025-01-01", "A", "B", 0, 0), row("2025-01-02", "B", "A", 0, 0)])
    assert m1_lambdas(fit_m1(training), "A", "B") == (0.0, 0.0)


def test_explicit_shrinkage_changes_unobserved_rate_only_when_requested() -> None:
    training = frame([row("2025-01-01", "A", "B", 2, 0), row("2025-01-02", "B", "A", 1, 1)])
    plain, shrunk = fit_m1(training, 0), fit_m1(training, 2)
    assert plain.shrinkage == 0 and shrunk.shrinkage == 2
    assert plain.home_scored["A"] != shrunk.home_scored["A"]


def test_unscaled_brier_definition() -> None:
    p = np.array([[0.5, 0.3, 0.2]])
    y = one_hot(["H"])
    assert np.isclose(brier_losses(p, y)[0], 0.25 + 0.09 + 0.04)


def test_rps_ordered_and_divided_by_two() -> None:
    p = np.array([[0.5, 0.3, 0.2]])
    y = one_hot(["H"])
    assert np.isclose(rps_losses(p, y)[0], ((-0.5) ** 2 + (-0.2) ** 2) / 2)


def test_invalid_odds_triplet_is_excluded() -> None:
    test = frame([row("2025-01-01", "A", "B", 1, 0), row("2025-01-02", "C", "D", 1, 1, AvgCA="1")])
    _, valid, excluded = market_probabilities(test)
    assert valid.tolist() == [True, False]
    assert "odds must" in excluded.iloc[0].reason


def test_loader_rejects_decimal_goals(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    write_results(path, [{"Date": "01/01/2025", "HomeTeam": "A", "AwayTeam": "B", "FTHG": "1.0", "FTAG": "0", "FTR": "H"}])
    with pytest.raises(DataValidationError, match="nonnegative"):
        load_matches(path, "partial")


def test_loader_rejects_bad_result_code(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    write_results(path, [{"Date": "01/01/2025", "HomeTeam": "A", "AwayTeam": "B", "FTHG": "1", "FTAG": "0", "FTR": "X"}])
    with pytest.raises(DataValidationError, match="FTR must"):
        load_matches(path, "partial")


def test_loader_rejects_inconsistent_result(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    write_results(path, [{"Date": "01/01/2025", "HomeTeam": "A", "AwayTeam": "B", "FTHG": "0", "FTAG": "1", "FTR": "H"}])
    with pytest.raises(DataValidationError, match="inconsistent"):
        load_matches(path, "partial")


def test_loader_rejects_duplicate_fixture_date(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    rows = [
        {"Date": "01/01/2025", "HomeTeam": "A", "AwayTeam": "B", "FTHG": "1", "FTAG": "0", "FTR": "H"},
        {"Date": "01/01/2025", "HomeTeam": "A", "AwayTeam": "B", "FTHG": "2", "FTAG": "0", "FTR": "H"},
    ]
    write_results(path, rows)
    with pytest.raises(DataValidationError, match="duplicate"):
        load_matches(path, "partial")


def test_partial_mode_excludes_unplayed_rows(tmp_path: Path) -> None:
    path = tmp_path / "partial.csv"
    rows = [
        {"Date": "01/01/2025", "HomeTeam": "A", "AwayTeam": "B", "FTHG": "1", "FTAG": "0", "FTR": "H"},
        {"Date": "02/01/2025", "HomeTeam": "B", "AwayTeam": "A", "FTHG": "", "FTAG": "", "FTR": ""},
    ]
    write_results(path, rows)
    loaded, summary = load_matches(path, "partial")
    assert len(loaded) == 1 and summary.incomplete_rows_excluded == 1 and not summary.complete_schedule


def test_complete_mode_accepts_20_team_double_round_robin(tmp_path: Path) -> None:
    teams = [f"T{i:02d}" for i in range(20)]
    rows = []
    day = pd.Timestamp("2025-01-01")
    for h in teams:
        for a in teams:
            if h != a:
                rows.append({"Date": day.strftime("%d/%m/%Y"), "HomeTeam": h, "AwayTeam": a, "FTHG": "1", "FTAG": "0", "FTR": "H"})
                day += pd.Timedelta(days=1)
    path = tmp_path / "complete.csv"
    write_results(path, rows)
    loaded, summary = load_matches(path, "complete")
    assert len(loaded) == 380 and summary.complete_schedule and summary.teams == 20


def test_standings_sort_is_deterministic_alphabetical_fallback() -> None:
    table = rebuild_standings(frame([row("2025-01-01", "B", "A", 0, 0)]))
    assert table.Team.tolist() == ["A", "B"]


def test_walk_forward_skips_entire_warmup_date_batch() -> None:
    matches = frame([
        row("2025-01-01", "A", "B", 1, 0), row("2025-01-01", "C", "D", 1, 0), row("2025-01-01", "E", "F", 1, 0),
        row("2025-01-02", "A", "C", 1, 1), row("2025-01-02", "B", "D", 0, 1),
    ])
    result = walk_forward(matches, warmup=2)
    assert result.skipped_warmup_rows == 3
    assert set(result.predictions.training_count) == {3}
    assert set(result.predictions.latest_training_date) == {"2025-01-01"}


def test_walk_forward_earlier_prediction_is_invariant_to_later_result() -> None:
    base = frame([
        row("2025-01-01", "A", "B", 1, 0), row("2025-01-01", "C", "D", 0, 0),
        row("2025-01-02", "A", "C", 2, 0), row("2025-01-02", "B", "D", 1, 2),
        row("2025-01-03", "A", "D", 0, 0), row("2025-01-03", "B", "C", 1, 1),
    ])
    changed = base.copy()
    changed.loc[changed.Date == pd.Timestamp("2025-01-03"), ["FTHG", "FTAG", "FTR"]] = [9, 0, "H"]
    p1, p2 = walk_forward(base, warmup=2).predictions, walk_forward(changed, warmup=2).predictions
    earliest1 = p1.loc[p1.Date == pd.Timestamp("2025-01-02"), ["M0_H", "M0_D", "M0_A", "M1_H", "M1_D", "M1_A"]]
    earliest2 = p2.loc[p2.Date == pd.Timestamp("2025-01-02"), earliest1.columns]
    assert np.allclose(earliest1, earliest2)


def test_date_block_bootstrap_is_seed_reproducible() -> None:
    losses = pd.DataFrame({"Date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02"]), "M0_brier": [1, 2, 3], "M1_brier": [0, 1, 1], "M0_rps": [1, 2, 3], "M1_rps": [0, 1, 1]})
    assert date_block_bootstrap(losses, "brier", 50, 9) == date_block_bootstrap(losses, "brier", 50, 9)


def test_halfway_boundary_never_splits_date() -> None:
    matches = frame([row("2025-01-01", "A", "B", 1, 0), row("2025-01-01", "C", "D", 1, 0), row("2025-01-02", "A", "C", 0, 0)])
    base, future, boundary = halfway_boundary(matches, target_rows=1)
    assert len(base) == 2 and len(future) == 1 and boundary == pd.Timestamp("2025-01-01")


def test_simulation_points_conservation_and_reproducibility() -> None:
    base = frame([row("2025-01-01", "A", "B", 1, 0), row("2025-01-02", "B", "C", 0, 0), row("2025-01-03", "C", "A", 1, 2)])
    future = frame([row("2025-01-04", "A", "C", 0, 0), row("2025-01-05", "B", "A", 0, 0), row("2025-01-06", "C", "B", 0, 0)])
    a = simulate_remaining_season(base, future, simulations=300, seed=7)
    b = simulate_remaining_season(base, future, simulations=300, seed=7)
    assert a.points_conservation_ok and np.array_equal(a.points, b.points)
    assert np.isclose(a.champion_weight.sum(), 1) and np.isclose(a.top4_weight.sum(), 3)


def test_monte_carlo_qa_reports_seed_reproducibility_and_skellam() -> None:
    qa = monte_carlo_qa(1.4, 1.0, seed=12, sizes=(1000,))
    assert qa["same_seed_reproducible"] and qa["grid_skellam_max_abs_difference"] < 1e-8


def test_calibration_has_bin_counts() -> None:
    predictions = frame([row("2025-01-01", "A", "B", 1, 0), row("2025-01-02", "B", "A", 0, 0)])
    for label, values in {"M1_H": [0.5, 0.3], "M1_D": [0.3, 0.4], "M1_A": [0.2, 0.3]}.items():
        predictions[label] = values
    calibration = calibration_table(predictions)
    assert calibration["count"].sum() == 6


def test_goodness_fit_pools_sparse_bins_and_bootstraps() -> None:
    matches = frame([row(f"2025-01-{i+1:02d}", "A", "B", i % 3, (i + 1) % 3) for i in range(10)])
    table, result = pooled_poisson_gof(matches, replicates=20, seed=2)
    assert len(table) >= 1 and 0 <= result["parametric_bootstrap_p_value"] <= 1
