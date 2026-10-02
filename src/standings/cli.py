"""Command-line interface for reproducible Poisson standings modeling."""
from __future__ import annotations

import argparse
from datetime import timezone
from datetime import datetime
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from .data import DataValidationError, load_matches, rebuild_standings
from .diagnostics import calibration_table, pooled_poisson_gof
from .evaluation import date_block_bootstrap, score_summary, walk_forward
from .live import create_live_predictions, manual_download, score_live_predictions
from .models import fit_m0, fit_m1, m0_lambdas, m1_lambdas
from .probability import outcome_probabilities, skellam_probabilities
from .reporting import (
    plot_calibration,
    plot_forecast_intervals,
    plot_goodness_fit,
    plot_score_comparison,
    plot_score_matrix,
    sha256,
    write_json,
    write_report,
)
from .simulation import monte_carlo_qa, simulate_halfway_season


def _as_of(value: str) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("--as-of must be an ISO date such as 2026-01-01")
    return pd.Timestamp(parsed).normalize()


def _json_print(data: dict) -> None:
    print(json.dumps(data, indent=2, default=str))


def _write_hand_checks(out: Path, predictions: pd.DataFrame) -> list[str]:
    """Write five independent compact CSV inputs plus one Excel-ready formula table."""
    destination = out / "hand_checks"
    destination.mkdir(exist_ok=True)
    selection = predictions.iloc[np.unique(np.linspace(0, len(predictions) - 1, 5, dtype=int))].copy()
    written: list[str] = []
    formulas: list[dict] = []
    for number, row in enumerate(selection.itertuples(index=False), start=1):
        input_path = destination / f"hand_check_input_{number:02d}.csv"
        pd.DataFrame([{
            "Date": pd.Timestamp(row.Date).date().isoformat(),
            "HomeTeam": row.HomeTeam,
            "AwayTeam": row.AwayTeam,
            "TrainingRows": row.training_count,
            "LatestTrainingDate": row.latest_training_date,
        }]).to_csv(input_path, index=False)
        written.append(str(input_path.relative_to(out)))
        # Refit exactly as of this recorded training cutoff to make the
        # hand-calculation inputs independently reproducible in a spreadsheet.
        # Formula terms are reconstructed below by calling code in run_analysis.
        formulas.append({
            "Check": number,
            "Date": pd.Timestamp(row.Date).date().isoformat(),
            "HomeTeam": row.HomeTeam,
            "AwayTeam": row.AwayTeam,
            "TrainingRows": row.training_count,
            "LatestTrainingDate": row.latest_training_date,
            "M1_HomeLambda": row.M1_lambda_home,
            "M1_AwayLambda": row.M1_lambda_away,
            "HomeFormula": "=(HomeHomeScoredRate/LeagueHomeMean)*(AwayAwayConcededRate/LeagueHomeMean)*LeagueHomeMean",
            "AwayFormula": "=(AwayAwayScoredRate/LeagueAwayMean)*(HomeHomeConcededRate/LeagueAwayMean)*LeagueAwayMean",
        })
    formula_path = out / "hand_checks.csv"
    pd.DataFrame(formulas).to_csv(formula_path, index=False)
    written.append(str(formula_path.relative_to(out)))
    return written


def _enrich_hand_formula_table(out: Path, matches: pd.DataFrame) -> None:
    path = out / "hand_checks.csv"
    table = pd.read_csv(path)
    additions: list[dict] = []
    for row in table.itertuples(index=False):
        train = matches.loc[matches["Date"] < pd.Timestamp(row.Date)]
        fit = fit_m1(train)
        home_rows = train.loc[train["HomeTeam"] == row.HomeTeam]
        away_rows = train.loc[train["AwayTeam"] == row.AwayTeam]
        additions.append({
            "LeagueHomeGoalsSum": int(train["FTHG"].sum()),
            "LeagueHomeMatches": int(len(train)),
            "LeagueAwayGoalsSum": int(train["FTAG"].sum()),
            "LeagueAwayMatches": int(len(train)),
            "HomeHomeGoalsScoredSum": int(home_rows["FTHG"].sum()),
            "HomeHomeMatches": int(len(home_rows)),
            "AwayAwayGoalsConcededSum": int(away_rows["FTHG"].sum()),
            "AwayAwayMatches": int(len(away_rows)),
            "AwayAwayGoalsScoredSum": int(away_rows["FTAG"].sum()),
            "HomeHomeGoalsConcededSum": int(home_rows["FTAG"].sum()),
            "LeagueHomeMean": fit.home_mean,
            "LeagueAwayMean": fit.away_mean,
            "HomeHomeScoredRate": fit.home_scored.get(row.HomeTeam, fit.home_mean),
            "AwayAwayConcededRate": fit.away_conceded.get(row.AwayTeam, fit.home_mean),
            "AwayAwayScoredRate": fit.away_scored.get(row.AwayTeam, fit.away_mean),
            "HomeHomeConcededRate": fit.home_conceded.get(row.HomeTeam, fit.away_mean),
        })
    expanded = pd.concat([table, pd.DataFrame(additions)], axis=1)
    # Move numeric formula ingredients before the recorded results/formula text
    preferred = ["Check", "Date", "HomeTeam", "AwayTeam", "TrainingRows", "LatestTrainingDate", "LeagueHomeGoalsSum", "LeagueHomeMatches", "LeagueAwayGoalsSum", "LeagueAwayMatches", "HomeHomeGoalsScoredSum", "HomeHomeMatches", "AwayAwayGoalsConcededSum", "AwayAwayMatches", "AwayAwayGoalsScoredSum", "HomeHomeGoalsConcededSum", "LeagueHomeMean", "LeagueAwayMean", "HomeHomeScoredRate", "AwayAwayConcededRate", "AwayAwayScoredRate", "HomeHomeConcededRate", "M1_HomeLambda", "M1_AwayLambda", "HomeFormula", "AwayFormula"]
    expanded.loc[:, preferred].to_csv(path, index=False)
    # Alias retained for collaborators who had already adopted the earlier
    # descriptive filename; both files have exactly the same workbook inputs.
    expanded.loc[:, preferred].to_csv(out / "hand_check_formula_table.csv", index=False)


def run_analysis(data: str | Path, out: str | Path, seed: int = 3315, simulations: int = 10_000, shrinkage: float = 0.0) -> dict:
    """Run the complete 2025/26 completed-season backtest and write artifacts."""
    source = Path(data)
    out = Path(out)
    figures = out / "figures"
    out.mkdir(parents=True, exist_ok=True)
    figures.mkdir(exist_ok=True)
    matches, validation = load_matches(source, mode="complete")
    if shrinkage < 0:
        raise ValueError("--shrinkage must be nonnegative")

    walk = walk_forward(matches, warmup=100, shrinkage=shrinkage)
    if walk.common_predictions.empty:
        raise ValueError("no valid AvgCH/AvgCD/AvgCA triplets in walk-forward rows; common comparison cannot be calculated")
    scores, losses = score_summary(walk.common_predictions)
    bootstrap = [
        date_block_bootstrap(losses, "brier", replicates=2000, seed=seed),
        date_block_bootstrap(losses, "rps", replicates=2000, seed=seed + 1),
    ]
    actual = rebuild_standings(matches)
    simulation, boundary, future = simulate_halfway_season(matches, simulations=simulations, seed=seed, shrinkage=shrinkage)
    forecast = simulation.forecast_table(actual)
    goodness_table, goodness = pooled_poisson_gof(matches, replicates=1000, seed=seed)

    selected = future.iloc[0]
    boundary_fit = fit_m1(boundary, shrinkage=shrinkage)
    selected_lh, selected_la = m1_lambdas(boundary_fit, selected.HomeTeam, selected.AwayTeam)
    selected_grid = outcome_probabilities(selected_lh, selected_la)
    qa = monte_carlo_qa(selected_lh, selected_la, seed=seed)
    qa.update({
        "season_simulations": simulations,
        "simulation_boundary_date": simulation.boundary_date.date().isoformat(),
        "simulation_training_rows": simulation.training_rows,
        "simulation_remaining_rows": simulation.remaining_rows,
        "points_conservation_ok": simulation.points_conservation_ok,
        "common_odds_sample": int(len(walk.common_predictions)),
        "odds_rows_excluded": int(len(walk.excluded_odds_rows)),
        "final_points_mae": float(np.abs(forecast["ExpectedPts"] - forecast["ActualPts"]).mean()),
        "max_grid_tail": max(float(walk.max_grid_tail), float(selected_grid.tail_mass)),
        "selected_fixture": {"Date": pd.Timestamp(selected.Date).date().isoformat(), "HomeTeam": selected.HomeTeam, "AwayTeam": selected.AwayTeam},
    })

    # Data and tables
    walk.predictions.to_csv(out / "walk_forward_predictions.csv", index=False)
    walk.common_predictions.to_csv(out / "walk_forward_common_odds_sample.csv", index=False)
    walk.excluded_odds_rows.to_csv(out / "walk_forward_excluded_odds.csv", index=False)
    scores.to_csv(out / "walk_forward_scores.csv", index=False)
    losses.to_csv(out / "walk_forward_row_losses.csv", index=False)
    actual.to_csv(out / "actual_rebuilt_table.csv", index=False)
    forecast.to_csv(out / "halfway_forecast_table.csv", index=False)
    goodness_table.to_csv(out / "goals_goodness_of_fit.csv", index=False)
    calibration = calibration_table(walk.common_predictions, "M1")
    calibration.to_csv(out / "calibration_m1.csv", index=False)
    hand_files = _write_hand_checks(out, walk.predictions)
    _enrich_hand_formula_table(out, matches)

    # Export the classroom derivation inputs, not only rendered figures.
    strength_rows = []
    for team in simulation.teams:
        hs = boundary_fit.home_scored.get(team, boundary_fit.home_mean)
        hc = boundary_fit.home_conceded.get(team, boundary_fit.away_mean)
        ass = boundary_fit.away_scored.get(team, boundary_fit.away_mean)
        ac = boundary_fit.away_conceded.get(team, boundary_fit.home_mean)
        strength_rows.append({
            "Team": team, "TrainingThrough": simulation.boundary_date.date().isoformat(),
            "HomeScoredRate": hs, "HomeConcededRate": hc,
            "AwayScoredRate": ass, "AwayConcededRate": ac,
            "HomeAttackRatio": hs / boundary_fit.home_mean if boundary_fit.home_mean else 1.0,
            "AwayConcessionRatio": ac / boundary_fit.home_mean if boundary_fit.home_mean else 1.0,
            "AwayAttackRatio": ass / boundary_fit.away_mean if boundary_fit.away_mean else 1.0,
            "HomeConcessionRatio": hc / boundary_fit.away_mean if boundary_fit.away_mean else 1.0,
        })
    pd.DataFrame(strength_rows).to_csv(out / "fitted_strengths_halfway.csv", index=False)
    pd.DataFrame(selected_grid.matrix).rename_axis("HomeGoals").to_csv(out / "selected_score_matrix.csv")

    # Plot suite requested by the project plan.
    plot_score_comparison(scores, figures / "score_comparison.png")
    plot_calibration(calibration, figures / "calibration_m1.png")
    plot_forecast_intervals(forecast, figures / "forecast_intervals.png")
    plot_score_matrix(selected_grid, selected.HomeTeam, selected.AwayTeam, figures / "selected_score_matrix.png")
    plot_goodness_fit(goodness_table, figures / "goals_goodness_of_fit.png")

    source_metadata = {
        "input_path": str(source),
        "sha256": sha256(source),
        "provider": "football-data.co.uk",
        "provenance_note": "The input SHA-256 identifies the actual local file. Acquisition history, where supplied, is recorded separately in data/provenance.json; do not infer byte-exact remote provenance for other user-provided files.",
        "run_created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_parameters": {"seed": seed, "simulations": simulations, "shrinkage": shrinkage, "warmup": 100, "halfway_target": 190},
        "runtime_versions": {"python": platform.python_version(), **{name: version(name) for name in ("numpy", "pandas", "scipy", "matplotlib", "tabulate")}},
        "analysis_columns": ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "AvgCH", "AvgCD", "AvgCA"],
        "excluded_columns": "xG/HxG/AxG and all Pinnacle-derived odds are not used in the core model or benchmark.",
    }
    write_json(out / "validation.json", validation.to_dict())
    write_json(out / "source_metadata.json", source_metadata)
    write_json(out / "walk_forward_metadata.json", walk.metadata())
    write_json(out / "bootstrap_m0_minus_m1.json", bootstrap)
    write_json(out / "goals_goodness_of_fit.json", goodness)
    write_json(out / "qa_checks.json", qa)

    listed = [
        "validation.json", "source_metadata.json", "walk_forward_metadata.json", "walk_forward_predictions.csv", "walk_forward_common_odds_sample.csv", "walk_forward_excluded_odds.csv", "walk_forward_scores.csv", "bootstrap_m0_minus_m1.json", "actual_rebuilt_table.csv", "halfway_forecast_table.csv", "goals_goodness_of_fit.csv", "goals_goodness_of_fit.json", "calibration_m1.csv", "qa_checks.json", "hand_check_formula_table.csv", *hand_files,
        "fitted_strengths_halfway.csv", "selected_score_matrix.csv",
        "figures/score_comparison.png", "figures/calibration_m1.png", "figures/forecast_intervals.png", "figures/selected_score_matrix.png", "figures/goals_goodness_of_fit.png",
    ]
    write_report(out / "report.md", validation.to_dict(), source_metadata, scores, bootstrap, forecast, goodness, qa, listed)
    return {
        "out": str(out),
        "report": str(out / "report.md"),
        "rows": len(matches),
        "walk_forward_common_sample": len(walk.common_predictions),
        "simulation_boundary": simulation.boundary_date.date().isoformat(),
        "simulations": simulations,
        "scores": scores.to_dict(orient="records"),
    }


def command_predict(args: argparse.Namespace) -> dict:
    matches, summary = load_matches(args.data, mode="partial")
    as_of = _as_of(args.as_of)
    training = matches.loc[matches["Date"] < as_of]
    if training.empty:
        raise ValueError("no completed records are strictly before --as-of")
    m0 = fit_m0(training)
    m1 = fit_m1(training, shrinkage=args.shrinkage)
    m0_lam = m0_lambdas(m0, args.home, args.away)
    m1_lam = m1_lambdas(m1, args.home, args.away)
    m0_grid, m1_grid = outcome_probabilities(*m0_lam), outcome_probabilities(*m1_lam)
    return {
        "as_of": as_of.date().isoformat(),
        "training_rule": "Date strictly before as_of",
        "training_count": len(training),
        "latest_training_date": training["Date"].max().date().isoformat(),
        "home": args.home,
        "away": args.away,
        "shrinkage": args.shrinkage,
        "M0": {"lambdas": m0_lam, **m0_grid.to_dict()},
        "M1": {"lambdas": m1_lam, **m1_grid.to_dict()},
        "data_validation": summary.to_dict(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="standings", description="Independent Poisson Premier League match and season modeling")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run complete-season backtest, frozen simulation, diagnostics, and plots")
    run.add_argument("--data", required=True, help="completed football-data.co.uk-style CSV")
    run.add_argument("--out", required=True, help="output directory")
    run.add_argument("--seed", type=int, default=3315)
    run.add_argument("--simulations", type=int, default=10_000)
    run.add_argument("--shrinkage", type=float, default=0.0, help="explicit M1 pseudo-match shrinkage; default 0 (unsmoothed)")

    download = sub.add_parser("download", help="user-invoked one-off data download; never schedules or refreshes automatically")
    download.add_argument("--season", required=True, help="four-digit season, e.g. 2526")
    download.add_argument("--output", required=True, help="local CSV destination")
    download.add_argument("--timeout", type=float, default=30.0)

    predict = sub.add_parser("predict", help="predict one fixture from results strictly before an as-of date")
    predict.add_argument("--data", required=True)
    predict.add_argument("--home", required=True)
    predict.add_argument("--away", required=True)
    predict.add_argument("--as-of", required=True)
    predict.add_argument("--shrinkage", type=float, default=0.0)

    live = sub.add_parser("live", help="write immutable timestamped future-fixture forecasts from a strict as-of snapshot")
    live.add_argument("--data", required=True)
    live.add_argument("--fixtures", required=True, help="CSV with Date, HomeTeam, AwayTeam")
    live.add_argument("--out", required=True)
    live.add_argument("--as-of", required=True)
    live.add_argument("--seed", type=int, default=3315)

    score = sub.add_parser("score-live", help="score an immutable live forecast log where actual results now exist")
    score.add_argument("--predictions", required=True)
    score.add_argument("--data", required=True)
    score.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run_analysis(args.data, args.out, args.seed, args.simulations, args.shrinkage)
        elif args.command == "download":
            result = manual_download(args.season, args.output, args.timeout)
        elif args.command == "predict":
            result = command_predict(args)
        elif args.command == "live":
            result = create_live_predictions(args.data, args.fixtures, args.out, args.as_of, args.seed)
        elif args.command == "score-live":
            result = score_live_predictions(args.predictions, args.data, args.out)
        else:  # pragma: no cover
            parser.error("unknown command")
            return 2
        _json_print(result)
        return 0
    except (DataValidationError, ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
