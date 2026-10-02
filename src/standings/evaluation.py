"""Leakage-safe retrospective prediction and proper-score evaluation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .models import fit_m0, fit_m1, m0_lambdas, m1_lambdas
from .probability import outcome_probabilities

OUTCOMES = ("H", "D", "A")
ODDS_COLUMNS = ("AvgCH", "AvgCD", "AvgCA")  # fixed before analysis; no Pinnacle-derived column


@dataclass
class WalkForwardResult:
    predictions: pd.DataFrame
    common_predictions: pd.DataFrame
    warmup_target: int
    skipped_warmup_rows: int
    skipped_warmup_dates: list[str]
    excluded_odds_rows: pd.DataFrame
    max_grid_tail: float

    def metadata(self) -> dict:
        return {
            "warmup_target": self.warmup_target,
            "skipped_warmup_rows": self.skipped_warmup_rows,
            "skipped_warmup_dates": self.skipped_warmup_dates,
            "odds_columns_fixed_upfront": list(ODDS_COLUMNS),
            "common_odds_sample": int(len(self.common_predictions)),
            "odds_rows_excluded": int(len(self.excluded_odds_rows)),
            "max_adaptive_grid_tail": self.max_grid_tail,
        }


def one_hot(outcomes: Iterable[str]) -> np.ndarray:
    values = list(outcomes)
    result = np.zeros((len(values), 3), dtype=float)
    mapping = {"H": 0, "D": 1, "A": 2}
    for i, value in enumerate(values):
        if value not in mapping:
            raise ValueError(f"unknown outcome {value!r}")
        result[i, mapping[value]] = 1.0
    return result


def brier_losses(probabilities: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Unscaled three-outcome Brier loss: sum of all three squared errors."""
    p, y = np.asarray(probabilities, float), np.asarray(actual, float)
    if p.shape != y.shape or p.ndim != 2 or p.shape[1] != 3:
        raise ValueError("probabilities and actual must both have shape (n, 3)")
    return ((p - y) ** 2).sum(axis=1)


def rps_losses(probabilities: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Ordered H/D/A ranked probability score, divided by 2."""
    p, y = np.asarray(probabilities, float), np.asarray(actual, float)
    if p.shape != y.shape or p.ndim != 2 or p.shape[1] != 3:
        raise ValueError("probabilities and actual must both have shape (n, 3)")
    return ((np.cumsum(p, axis=1)[:, :2] - np.cumsum(y, axis=1)[:, :2]) ** 2).sum(axis=1) / 2.0


def market_probabilities(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """De-margin the fixed AvgC odds triplet; reject any invalid complete triplet."""
    absent = [column for column in ODDS_COLUMNS if column not in frame.columns]
    if absent:
        values = np.full((len(frame), 3), np.nan)
        valid = np.zeros(len(frame), dtype=bool)
        excluded = pd.DataFrame({"reason": [f"missing column(s): {', '.join(absent)}"] * len(frame)}, index=frame.index)
        return values, valid, excluded
    odds = frame.loc[:, ODDS_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(odds).all(axis=1) & (odds > 1.0).all(axis=1)
    probabilities = np.full_like(odds, np.nan, dtype=float)
    inverse = 1.0 / odds[valid]
    probabilities[valid] = inverse / inverse.sum(axis=1, keepdims=True)
    reason = np.where(~np.isfinite(odds).all(axis=1), "non-finite or missing odds", np.where((odds <= 1.0).any(axis=1), "odds must all be > 1", ""))
    excluded = pd.DataFrame({"reason": reason[~valid]}, index=frame.index[~valid])
    return probabilities, valid, excluded


def walk_forward(matches: pd.DataFrame, warmup: int = 100, shrinkage: float = 0.0) -> WalkForwardResult:
    """Predict date batches with only strictly earlier **date** rows as training.

    If the nominal 100th match falls in a multi-game date batch, that whole
    date is skipped rather than training on a same-date match. Thus the number
    of scored rows is deliberately not assumed to be 280.
    """
    if warmup < 1:
        raise ValueError("warmup must be positive")
    ordered = matches.sort_values("Date", kind="stable").reset_index(drop=True)
    records: list[dict] = []
    skipped_dates: list[str] = []
    skipped_rows = 0
    max_tail = 0.0
    for _, batch in ordered.groupby("Date", sort=True):
        start = int(batch.index.min())
        date_text = pd.Timestamp(batch.iloc[0]["Date"]).date().isoformat()
        if start < warmup:
            skipped_dates.append(date_text)
            skipped_rows += len(batch)
            continue
        training = ordered.loc[ordered["Date"] < batch.iloc[0]["Date"]]
        # By construction this has exactly the rows preceding the whole date.
        m0 = fit_m0(training)
        m1 = fit_m1(training, shrinkage=shrinkage)
        training_date = pd.Timestamp(training["Date"].max()).date().isoformat()
        for row in batch.itertuples(index=False):
            m0_grid = outcome_probabilities(*m0_lambdas(m0, row.HomeTeam, row.AwayTeam))
            m1_grid = outcome_probabilities(*m1_lambdas(m1, row.HomeTeam, row.AwayTeam))
            max_tail = max(max_tail, m0_grid.tail_mass, m1_grid.tail_mass)
            records.append({
                "Date": row.Date,
                "HomeTeam": row.HomeTeam,
                "AwayTeam": row.AwayTeam,
                "FTHG": int(row.FTHG),
                "FTAG": int(row.FTAG),
                "FTR": row.FTR,
                "training_count": len(training),
                "latest_training_date": training_date,
                "M0_H": m0_grid.home, "M0_D": m0_grid.draw, "M0_A": m0_grid.away,
                "M1_H": m1_grid.home, "M1_D": m1_grid.draw, "M1_A": m1_grid.away,
                "M0_lambda_home": m0.home_mean, "M0_lambda_away": m0.away_mean,
                "M1_lambda_home": m1_lambdas(m1, row.HomeTeam, row.AwayTeam)[0],
                "M1_lambda_away": m1_lambdas(m1, row.HomeTeam, row.AwayTeam)[1],
                **{column: getattr(row, column, np.nan) for column in ODDS_COLUMNS},
            })
    prediction = pd.DataFrame(records)
    if prediction.empty:
        raise ValueError("no date batch remains after the warmup; supply more completed rows")
    market, valid, excluded = market_probabilities(prediction)
    prediction[["Market_H", "Market_D", "Market_A"]] = market
    prediction["market_valid"] = valid
    common = prediction.loc[valid].copy().reset_index(drop=True)
    excluded = excluded.copy()
    if not excluded.empty:
        excluded.insert(0, "Date", prediction.loc[excluded.index, "Date"].astype(str).to_numpy())
        excluded.insert(1, "HomeTeam", prediction.loc[excluded.index, "HomeTeam"].to_numpy())
        excluded.insert(2, "AwayTeam", prediction.loc[excluded.index, "AwayTeam"].to_numpy())
    return WalkForwardResult(prediction, common, warmup, skipped_rows, skipped_dates, excluded.reset_index(drop=True), max_tail)


def score_summary(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return model mean scores and the rowwise losses used for comparison."""
    if predictions.empty:
        raise ValueError("cannot score an empty prediction table")
    actual = one_hot(predictions["FTR"])
    loss_data: dict[str, np.ndarray] = {"Date": predictions["Date"].to_numpy()}
    summary: list[dict] = []
    for label in ("M0", "M1", "Market"):
        probs = predictions[[f"{label}_H", f"{label}_D", f"{label}_A"]].to_numpy(float)
        brier = brier_losses(probs, actual)
        rps = rps_losses(probs, actual)
        loss_data[f"{label}_brier"] = brier
        loss_data[f"{label}_rps"] = rps
        summary.append({"Model": label, "N": len(predictions), "Brier_unscaled": float(brier.mean()), "RPS": float(rps.mean())})
    return pd.DataFrame(summary), pd.DataFrame(loss_data)


def date_block_bootstrap(losses: pd.DataFrame, metric: str, replicates: int = 2000, seed: int = 3315) -> dict:
    """Paired date-block bootstrap CI for mean M0 minus M1 loss.

    Positive values favor M1 because lower proper-score loss is better.
    """
    if metric not in {"brier", "rps"}:
        raise ValueError("metric must be brier or rps")
    if replicates < 1:
        raise ValueError("replicates must be positive")
    left = losses[f"M0_{metric}"].to_numpy(float)
    right = losses[f"M1_{metric}"].to_numpy(float)
    grouped = [group.index.to_numpy() for _, group in losses.groupby("Date", sort=True)]
    if not grouped:
        raise ValueError("no date blocks to bootstrap")
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates, dtype=float)
    for i in range(replicates):
        selection = rng.integers(0, len(grouped), size=len(grouped))
        indices = np.concatenate([grouped[j] for j in selection])
        draws[i] = float(np.mean(left[indices] - right[indices]))
    observed = float(np.mean(left - right))
    return {
        "metric": metric,
        "contrast": "M0 minus M1 (positive favors M1)",
        "estimate": observed,
        "ci_95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "replicates": int(replicates),
        "seed": int(seed),
        "date_blocks": len(grouped),
    }
