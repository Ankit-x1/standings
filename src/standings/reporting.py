"""Output artifacts: CSV/JSON-friendly tables, plots, and a transparent report."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_score_comparison(scores: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(scores))
    width = 0.36
    ax.bar(x - width / 2, scores["Brier_unscaled"], width, label="Brier (unscaled)")
    ax.bar(x + width / 2, scores["RPS"], width, label="RPS")
    ax.set_xticks(x, scores["Model"])
    ax.set_ylabel("Mean loss (lower is better)")
    ax.set_title("Walk-forward proper-score comparison (common valid-odds rows)")
    ax.legend()
    _save(fig, path)


def plot_calibration(calibration: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="perfect calibration")
    sizes = 18 + 3 * calibration["count"].to_numpy()
    ax.scatter(calibration["mean_predicted"], calibration["observed_frequency"], s=sizes, alpha=0.75, label="M1 bins")
    for row in calibration.itertuples(index=False):
        ax.annotate(str(row.count), (row.mean_predicted, row.observed_frequency), xytext=(3, 3), textcoords="offset points", fontsize=8)
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted event probability", ylabel="Observed event frequency", title="Ternary calibration; labels are bin counts")
    ax.legend(loc="upper left")
    _save(fig, path)


def plot_forecast_intervals(forecast: pd.DataFrame, path: Path) -> None:
    ordered = forecast.sort_values("ExpectedRank", kind="stable").copy()
    y = np.arange(len(ordered))
    expected = ordered["ExpectedPts"].to_numpy()
    lo = ordered["Pts_p05"].to_numpy()
    hi = ordered["Pts_p95"].to_numpy()
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.errorbar(expected, y, xerr=np.vstack([expected - lo, hi - expected]), fmt="o", capsize=3, label="90% simulated interval")
    if "ActualPts" in ordered:
        ax.scatter(ordered["ActualPts"], y, marker="x", color="black", label="actual points")
    ax.set_yticks(y, ordered["Team"])
    ax.invert_yaxis()
    ax.set_xlabel("Points")
    ax.set_title("Frozen half-season Model 1 forecast intervals")
    ax.legend()
    _save(fig, path)


def plot_score_matrix(grid: Any, home: str, away: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5.8))
    image = ax.imshow(grid.matrix, origin="lower", aspect="auto", cmap="Blues")
    shown = min(grid.max_goals, 10)
    ticks = np.arange(shown + 1)
    ax.set_xticks(ticks, ticks)
    ax.set_yticks(ticks, ticks)
    ax.set_xlabel(f"{away} goals")
    ax.set_ylabel(f"{home} goals")
    ax.set_title(f"Adaptive Poisson score matrix: {home} vs {away} (shown 0–{shown})")
    fig.colorbar(image, ax=ax, label="Probability")
    _save(fig, path)


def plot_goodness_fit(gof: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(gof))
    ax.bar(x - 0.18, gof["Observed"], 0.36, label="observed")
    ax.bar(x + 0.18, gof["ExpectedPoisson"], 0.36, label="Poisson expected")
    ax.set_xticks(x, gof["Goals"])
    ax.set_xlabel("Goals category (pooled as needed)")
    ax.set_ylabel("Team-match counts")
    ax.set_title("Exploratory pooled Poisson goodness of fit")
    ax.legend()
    _save(fig, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def write_report(
    path: Path,
    validation: dict,
    source_metadata: dict,
    scores: pd.DataFrame,
    bootstrap: list[dict],
    forecast: pd.DataFrame,
    gof: dict,
    qa: dict,
    files: list[str],
) -> None:
    score_md = scores.to_markdown(index=False, floatfmt=".6f")
    forecast_md = forecast[[c for c in ["Team", "ExpectedPts", "Pts_p05", "Pts_p95", "ExpectedRank", "ChampionProb", "Top4Prob", "RelegationProb", "ActualPts", "ActualRank_display", "ActualPtsIn90Interval"] if c in forecast]].to_markdown(index=False, floatfmt=".3f")
    bootstrap_lines = "\n".join(f"- **{item['metric'].upper()} M0 − M1:** {item['estimate']:.6f}; 95% date-block bootstrap CI [{item['ci_95'][0]:.6f}, {item['ci_95'][1]:.6f}] ({item['replicates']} replicates; positive favors M1)." for item in bootstrap)
    coverage = float(forecast["ActualPtsIn90Interval"].mean()) if "ActualPtsIn90Interval" in forecast else float("nan")
    report = f"""# Premier League independent-Poisson modeling run

## Scope and provenance

- **Input:** `{source_metadata['input_path']}`; local SHA-256 `{source_metadata['sha256']}`.
- **Provider/source:** football-data.co.uk Premier League CSV. This analysis uses only date, teams, final goals/result, and the fixed `AvgCH`, `AvgCD`, `AvgCA` closing-odds benchmark. It does not use xG columns or Pinnacle-derived odds.
- **Frozen-file provenance:** `{source_metadata['provenance_note']}`
- **Validation:** {validation['result_rows']} completed rows, {validation['teams']} teams, {validation['date_min']} through {validation['date_max']}; complete schedule = **{validation['complete_schedule']}**. Unplayed rows excluded in partial mode: {validation['incomplete_rows_excluded']}.

## Model and evaluation choices

M0 uses league home/away goal means. M1 uses unsmoothed (unless explicitly selected) home attack × away defense ratios and the mirrored away expression. Score grids begin at 0–10 and grow until omitted joint mass is below `1e-8`; probabilities are then normalized and the tail is recorded. The standing display sorts **Pts, GD, GF, then alphabetically only as an unresolved-tie fallback**—it does not reproduce official head-to-head tiebreaks.

Walk-forward scoring uses only matches with **Date strictly earlier** than the forecast date. The first nominal 100 records are warm-up; the whole date batch containing them is excluded, so the scored count need not be 280. The market comparison uses one fixed AvgC triplet and all three methods are scored on its common valid-odds sample (**{qa['common_odds_sample']} rows; {qa['odds_rows_excluded']} excluded invalid-odds rows are listed in `walk_forward_excluded_odds.csv`**). Brier is the **unscaled** three-outcome sum of squared errors; RPS is ordered H/D/A and divided by 2.

## Walk-forward scores

{score_md}

{bootstrap_lines}

## Frozen half-season simulation

The boundary is the first complete date at/after 190 records. Model 1 is frozen there and `{qa['season_simulations']}` remaining-fixture seasons are simulated. Exact Pts/GD/GF ties receive average rank; tied groups crossing champion/top-4/relegation boundaries share slots fractionally. This is an approximation and **does not claim official qualification or tiebreak resolution**. The final-points **MAE is {qa['final_points_mae']:.3f}**. The actual 90% points-interval coverage is **{coverage:.1%}** across 20 teams; it is descriptive, not a required pass rate.

{forecast_md}

## QA and exploratory diagnostic

- Maximum recorded adaptive-grid tail: `{qa['max_grid_tail']:.3e}`; grid/Skellam maximum discrepancy: `{qa['grid_skellam_max_abs_difference']:.3e}`.
- Same-seed Monte Carlo reproduction: **{qa['same_seed_reproducible']}**. The frequency stability table records stochastic standardized discrepancies rather than promising a deterministic outcome.
- Simulated points conservation: **{qa['points_conservation_ok']}**.
- Goals diagnostic: pooled expected counts all at least 5 = **{gof['all_expected_at_least_5']}**; λ-hat = {gof['lambda_hat']:.4f}; parametric-bootstrap p-value = {gof['parametric_bootstrap_p_value']:.4f} ({gof['bootstrap_replicates']} replicates). {gof['limitation']}

## Limitations

Goals are modeled independently with static team rates at each fit. The approach omits injuries, tactics, red cards, changing strength, and official head-to-head tiebreakers. More simulations reduce Monte Carlo error but cannot cure model misspecification. These results make **no promise of model improvement** and do not verify an official final table unless an official table is separately supplied.

## Generated artifacts

""" + "\n".join(f"- `{name}`" for name in files) + "\n"
    path.write_text(report, encoding="utf-8")
