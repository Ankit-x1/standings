"""Synthetic-only QA tests for immutable live forecast logs and scoring."""
from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from standings.data import DataValidationError
from standings.live import _load_fixtures, create_live_predictions, score_live_predictions


RESULT_FIELDS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]


def utc_day() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()


def write_results(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_fixtures(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows, columns=["Date", "HomeTeam", "AwayTeam"]).to_csv(path, index=False)


def result(day: pd.Timestamp, home: str, away: str, home_goals: int, away_goals: int) -> dict:
    return {
        "Date": day.date().isoformat(),
        "HomeTeam": home,
        "AwayTeam": away,
        "FTHG": home_goals,
        "FTAG": away_goals,
        "FTR": "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D",
    }


def write_live_inputs(tmp_path: Path) -> tuple[Path, Path, pd.Timestamp]:
    """Write a minimal valid completed result file and return its training date."""
    training_day = utc_day() - timedelta(days=2)
    data = tmp_path / "results.csv"
    fixtures = tmp_path / "fixtures.csv"
    write_results(data, [result(training_day, "A", "B", 1, 0)])
    return data, fixtures, training_day


def score_data(tmp_path: Path) -> Path:
    data = tmp_path / "scoring-results.csv"
    write_results(data, [
        result(pd.Timestamp("2025-01-01"), "C", "D", 1, 0),
        result(pd.Timestamp("2025-01-03"), "A", "B", 1, 0),
        result(pd.Timestamp("2025-01-04"), "B", "A", 0, 0),
    ])
    return data


def prediction_row(
    day: str,
    home: str,
    away: str,
    *,
    created: str,
    status: str = "genuinely_prospective",
    m0: tuple[float, float, float] = (0.8, 0.1, 0.1),
    m1: tuple[float, float, float] = (0.4, 0.4, 0.2),
) -> dict:
    return {
        "Date": day,
        "HomeTeam": home,
        "AwayTeam": away,
        "as_of": "2025-01-02",
        "created_at_utc": created,
        "latest_training_date": "2025-01-01",
        "M0_H": m0[0],
        "M0_D": m0[1],
        "M0_A": m0[2],
        "M1_H": m1[0],
        "M1_D": m1[1],
        "M1_A": m1[2],
        "prospective_status": status,
    }


def write_prediction_log(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_empty_fixture_file_is_rejected_clearly(tmp_path: Path) -> None:
    fixtures = tmp_path / "empty-fixtures.csv"
    fixtures.write_text("", encoding="utf-8")
    with pytest.raises(DataValidationError, match="fixtures file is empty"):
        _load_fixtures(fixtures)
    write_fixtures(fixtures, [])
    with pytest.raises(DataValidationError, match="contains no fixture rows"):
        _load_fixtures(fixtures)


def test_live_creation_rejects_future_as_of_day(tmp_path: Path) -> None:
    data, fixtures, training_day = write_live_inputs(tmp_path)
    write_fixtures(fixtures, [{"Date": (utc_day() + timedelta(days=2)).date().isoformat(), "HomeTeam": "C", "AwayTeam": "D"}])
    with pytest.raises(ValueError, match="cannot be after the actual UTC creation day"):
        create_live_predictions(data, fixtures, tmp_path / "out", (training_day + timedelta(days=3)).date().isoformat())


def test_historical_fixture_log_is_labeled_retrospective(tmp_path: Path) -> None:
    data, fixtures, training_day = write_live_inputs(tmp_path)
    fixture_day = utc_day()
    write_fixtures(fixtures, [{"Date": fixture_day.date().isoformat(), "HomeTeam": "C", "AwayTeam": "D"}])
    logged = create_live_predictions(data, fixtures, tmp_path / "out", (training_day + timedelta(days=1)).date().isoformat())
    prediction = pd.read_csv(logged["csv"])
    assert prediction.loc[0, "prospective_status"] == "retrospective"
    assert logged["retrospective_count"] == 1


def test_future_fixture_log_is_labeled_genuinely_prospective(tmp_path: Path) -> None:
    data, fixtures, training_day = write_live_inputs(tmp_path)
    fixture_day = utc_day() + timedelta(days=1)
    write_fixtures(fixtures, [{"Date": fixture_day.date().isoformat(), "HomeTeam": "C", "AwayTeam": "D"}])
    logged = create_live_predictions(data, fixtures, tmp_path / "out", (training_day + timedelta(days=2)).date().isoformat())
    prediction = pd.read_csv(logged["csv"])
    assert prediction.loc[0, "prospective_status"] == "genuinely_prospective"
    assert logged["genuinely_prospective_count"] == 1


def test_live_creation_writes_two_immutable_logs_without_overwrite(tmp_path: Path) -> None:
    data, fixtures, training_day = write_live_inputs(tmp_path)
    write_fixtures(fixtures, [{"Date": (utc_day() + timedelta(days=1)).date().isoformat(), "HomeTeam": "C", "AwayTeam": "D"}])
    as_of = (training_day + timedelta(days=2)).date().isoformat()
    first = create_live_predictions(data, fixtures, tmp_path / "out", as_of)
    second = create_live_predictions(data, fixtures, tmp_path / "out", as_of)
    assert first["csv"] != second["csv"]
    assert Path(first["csv"]).exists() and Path(second["csv"]).exists()
    assert len(list((tmp_path / "out").glob("live_predictions_*.csv"))) == 2


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"M0_H": float("nan")}, "M0 H/D/A probabilities"),
        ({"M1_H": 1.1}, "M1 H/D/A probabilities"),
        ({"M0_A": 0.2}, "M0 H/D/A probabilities"),
    ],
)
def test_scoring_rejects_invalid_probability_triplets(tmp_path: Path, changes: dict, message: str) -> None:
    data = score_data(tmp_path)
    row = prediction_row("2025-01-03", "A", "B", created="2025-01-02T12:00:00+00:00")
    row.update(changes)
    predictions = tmp_path / "invalid-probabilities.csv"
    write_prediction_log(predictions, [row])
    with pytest.raises(DataValidationError, match=message):
        score_live_predictions(predictions, data, tmp_path / "out")


def test_scoring_recomputes_spoofed_prospective_status(tmp_path: Path) -> None:
    data = score_data(tmp_path)
    predictions = tmp_path / "spoofed-status.csv"
    write_prediction_log(predictions, [
        prediction_row("2025-01-03", "A", "B", created="2025-01-04T12:00:00+00:00", status="genuinely_prospective"),
    ])
    scored = score_live_predictions(predictions, data, tmp_path / "out")
    detail = pd.read_csv(scored["detail"])
    assert detail.loc[0, "logged_prospective_status"] == "genuinely_prospective"
    assert detail.loc[0, "prospective_status"] == "retrospective"
    assert scored["genuinely_prospective_rows_scored"] == 0
    assert scored["logged_prospective_status_mismatch_rows"] == 1


def test_scoring_rejects_duplicate_fixture_rows_in_log(tmp_path: Path) -> None:
    data = score_data(tmp_path)
    row = prediction_row("2025-01-03", "A", "B", created="2025-01-02T12:00:00+00:00")
    predictions = tmp_path / "duplicate-log.csv"
    write_prediction_log(predictions, [row, row])
    with pytest.raises(DataValidationError, match="duplicate Date/HomeTeam/AwayTeam fixture rows"):
        score_live_predictions(predictions, data, tmp_path / "out")


def test_scoring_rejects_non_strict_training_chronology(tmp_path: Path) -> None:
    data = score_data(tmp_path)
    row = prediction_row("2025-01-03", "A", "B", created="2025-01-02T12:00:00+00:00")
    row["latest_training_date"] = "2025-01-02"
    predictions = tmp_path / "bad-chronology.csv"
    write_prediction_log(predictions, [row])
    with pytest.raises(DataValidationError, match="latest_training_date must be strictly before as_of"):
        score_live_predictions(predictions, data, tmp_path / "out")


def test_scoring_reports_all_scored_and_prospective_only_separately(tmp_path: Path) -> None:
    data = score_data(tmp_path)
    predictions = tmp_path / "mixed-log.csv"
    write_prediction_log(predictions, [
        prediction_row("2025-01-03", "A", "B", created="2025-01-02T12:00:00+00:00", status="retrospective", m0=(0.8, 0.1, 0.1)),
        prediction_row("2025-01-04", "B", "A", created="2025-01-05T12:00:00+00:00", status="genuinely_prospective", m0=(0.1, 0.2, 0.7)),
        prediction_row("2025-01-05", "C", "A", created="2025-01-02T12:00:00+00:00", status="retrospective", m0=(0.2, 0.2, 0.6)),
    ])
    scored = score_live_predictions(predictions, data, tmp_path / "out")
    assert scored["metric_population"] == "all_scored_including_retrospective"
    assert scored["all_scored_including_retrospective"]["rows_scored"] == 2
    assert scored["prospective_only"]["rows_scored"] == 1
    assert scored["M0_mean_Brier_unscaled"] == scored["all_scored_including_retrospective"]["M0_mean_Brier_unscaled"]
    assert scored["M0_mean_Brier_unscaled"] != scored["prospective_only"]["M0_mean_Brier_unscaled"]
    assert scored["genuinely_prospective_rows_scored"] == 1
    assert scored["retrospective_rows_scored"] == 1
    assert scored["rows_unscored_or_postponed_no_completed_result"] == 1
    assert Path(scored["unscored_detail_csv"]).exists()
