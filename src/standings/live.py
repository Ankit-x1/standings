"""Manual download and timestamped live-forecast logging utilities.

No scheduler, polling loop, or automatic refresh is implemented. The download
function is intentionally a one-off command invoked by the user.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen
from uuid import uuid4

import numpy as np
import pandas as pd

from .data import DataValidationError, _parse_dates, load_matches
from .evaluation import brier_losses, one_hot, rps_losses
from .models import fit_m0, fit_m1, m0_lambdas, m1_lambdas
from .probability import outcome_probabilities
from .reporting import sha256, write_json


PROVIDER_NOTICE = (
    "football-data.co.uk states that its data is for private individual use and warns against commercial/data-training use and automated bots/scrapers. "
    "This command is a user-invoked one-off manual download only; it does not schedule or automate refreshes."
)


def manual_download(season: str, output: str | Path, timeout: float = 30.0) -> dict:
    """Download one season only when explicitly called from the CLI."""
    if not re.fullmatch(r"\d{4}", season):
        raise ValueError("season must be four digits, e.g. 2526")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
    request = Request(url, headers={"User-Agent": "Math3315-coursework-manual-download/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content = response.read()
    except Exception as exc:
        raise RuntimeError(f"manual download failed for {url}: {exc}") from exc
    if not content:
        raise RuntimeError("manual download returned an empty response")
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(output)
    metadata = {
        "season": season,
        "url": url,
        "output": str(output),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout,
        "bytes": len(content),
        "sha256": sha256(output),
        "acquisition": "direct HTTP response, saved as bytes by explicit user command",
        "line_separator_normalized": False,
        "provider_notice": PROVIDER_NOTICE,
    }
    write_json(output.with_suffix(output.suffix + ".metadata.json"), metadata)
    return metadata


def _parse_as_of(value: str) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("--as-of must be an ISO date such as 2026-09-21")
    return pd.Timestamp(parsed).normalize()


def _load_fixtures(path: str | Path) -> pd.DataFrame:
    try:
        fixtures = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(["fixtures file is empty; expected Date, HomeTeam, and AwayTeam columns"]) from exc
    except Exception as exc:
        raise DataValidationError([f"could not read fixtures: {exc}"]) from exc
    if fixtures.empty:
        raise DataValidationError(["fixtures file contains no fixture rows"])
    needed = ["Date", "HomeTeam", "AwayTeam"]
    missing = [column for column in needed if column not in fixtures.columns]
    if missing:
        raise DataValidationError([f"fixtures missing required column(s): {', '.join(missing)}"])
    fixtures = fixtures.loc[:, needed].copy()
    fixtures["Date"] = _parse_dates(fixtures["Date"])
    for column in ("HomeTeam", "AwayTeam"):
        fixtures[column] = fixtures[column].astype(str).str.strip()
    if fixtures.isna().any().any() or (fixtures[["HomeTeam", "AwayTeam"]] == "").any().any():
        raise DataValidationError(["fixtures require nonblank Date, HomeTeam, and AwayTeam"])
    if (fixtures["HomeTeam"] == fixtures["AwayTeam"]).any():
        raise DataValidationError(["a fixture cannot name the same team home and away"])
    if fixtures.duplicated(["Date", "HomeTeam", "AwayTeam"]).any():
        raise DataValidationError(["duplicate Date/HomeTeam/AwayTeam fixture input"])
    return fixtures.sort_values("Date", kind="stable").reset_index(drop=True)


def create_live_predictions(data: str | Path, fixtures_path: str | Path, output_dir: str | Path, as_of: str, seed: int = 3315) -> dict:
    """Freeze a date-safe M0/M1 forecast log; never overwrite prior logs."""
    as_of_date = _parse_as_of(as_of)
    created = datetime.now(timezone.utc)
    if as_of_date.date() > created.date():
        raise ValueError("--as-of cannot be after the actual UTC creation day")
    matches, summary = load_matches(data, mode="partial")
    fixtures = _load_fixtures(fixtures_path)
    if (fixtures["Date"] <= as_of_date).any():
        raise ValueError("all fixture dates must be strictly after --as-of (date-only input is treated conservatively)")
    training = matches.loc[matches["Date"] < as_of_date].copy()
    if training.empty:
        raise ValueError("no completed matches are strictly before --as-of")
    m0, m1 = fit_m0(training), fit_m1(training)
    created_day = created.date()
    rows = []
    for fixture in fixtures.itertuples(index=False):
        m0_grid = outcome_probabilities(*m0_lambdas(m0, fixture.HomeTeam, fixture.AwayTeam))
        m1_lambda = m1_lambdas(m1, fixture.HomeTeam, fixture.AwayTeam)
        m1_grid = outcome_probabilities(*m1_lambda)
        fixture_day = pd.Timestamp(fixture.Date).date()
        prospective = as_of_date.date() < fixture_day and created_day < fixture_day
        rows.append({
            "Date": fixture_day.isoformat(), "HomeTeam": fixture.HomeTeam, "AwayTeam": fixture.AwayTeam,
            "as_of": as_of_date.date().isoformat(), "created_at_utc": created.isoformat(),
            "training_count": len(training), "latest_training_date": pd.Timestamp(training["Date"].max()).date().isoformat(),
            "M0_lambda_home": m0.home_mean, "M0_lambda_away": m0.away_mean,
            "M0_H": m0_grid.home, "M0_D": m0_grid.draw, "M0_A": m0_grid.away,
            "M1_lambda_home": m1_lambda[0], "M1_lambda_away": m1_lambda[1],
            "M1_H": m1_grid.home, "M1_D": m1_grid.draw, "M1_A": m1_grid.away,
            "max_grid_tail": max(m0_grid.tail_mass, m1_grid.tail_mass),
            "prospective_status": "genuinely_prospective" if prospective else "retrospective",
            "prospective_criterion": "fixture Date > as_of AND UTC creation calendar day < fixture Date; date-only fixtures use this conservative cutoff",
        })
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    identifier = created.strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex[:8]
    csv_path = output_dir / f"live_predictions_{identifier}.csv"
    json_path = output_dir / f"live_predictions_{identifier}.json"
    if csv_path.exists() or json_path.exists():  # practically impossible but proves no overwrite behavior
        raise FileExistsError("immutable live log collision; rerun to create a new timestamped log")
    prediction = pd.DataFrame(rows)
    prediction.to_csv(csv_path, index=False)
    metadata = {
        "type": "immutable_live_prediction_log",
        "created_at_utc": created.isoformat(),
        "as_of": as_of_date.date().isoformat(),
        "training_rule": "completed results with Date strictly earlier than as_of",
        "data_validation": summary.to_dict(),
        "data_sha256": sha256(Path(data)),
        "fixtures_sha256": sha256(Path(fixtures_path)),
        "seed_recorded_for_reproducibility": int(seed),
        "prediction_csv": str(csv_path),
        "genuinely_prospective_count": int((prediction["prospective_status"] == "genuinely_prospective").sum()),
        "retrospective_count": int((prediction["prospective_status"] == "retrospective").sum()),
        "prospective_criterion": prediction.iloc[0]["prospective_criterion"] if len(prediction) else "no fixtures",
        "notice": "A historical as-of value alone does not make a log prospective. Creation time must precede the date-only fixture cutoff.",
    }
    write_json(json_path, metadata)
    return {"csv": str(csv_path), "metadata": str(json_path), **metadata}


def _prediction_csv_rows(mask: np.ndarray | pd.Series) -> str:
    """Return one-indexed CSV data-row numbers for concise validation errors."""
    positions = np.flatnonzero(np.asarray(mask, dtype=bool))[:5] + 2
    return ", ".join(str(int(position)) for position in positions)


def _parse_log_dates(prediction: pd.DataFrame, column: str) -> pd.Series:
    parsed = _parse_dates(prediction[column])
    if parsed.isna().any():
        raise DataValidationError([f"prediction log contains invalid {column} value(s); CSV row(s): {_prediction_csv_rows(parsed.isna())}"])
    return parsed


def _parse_log_utc_timestamps(values: pd.Series) -> pd.Series:
    """Require timezone-aware creation timestamps and normalize them to UTC."""
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")
    invalid = np.zeros(len(values), dtype=bool)
    for position, (index, raw) in enumerate(values.items()):
        try:
            timestamp = pd.Timestamp(raw)
        except (TypeError, ValueError, OverflowError):
            invalid[position] = True
            continue
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            invalid[position] = True
            continue
        parsed.at[index] = timestamp.tz_convert("UTC")
    if invalid.any():
        raise DataValidationError([
            "created_at_utc must contain finite, timezone-aware timestamps; "
            f"invalid prediction CSV row(s): {_prediction_csv_rows(invalid)}"
        ])
    return parsed


def _validate_prediction_probabilities(prediction: pd.DataFrame) -> None:
    """Validate every logged H/D/A triplet before any result merge or scoring."""
    for label in ("M0", "M1"):
        columns = [f"{label}_H", f"{label}_D", f"{label}_A"]
        probabilities = prediction.loc[:, columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        finite = np.isfinite(probabilities).all(axis=1)
        in_unit_interval = ((probabilities >= 0.0) & (probabilities <= 1.0)).all(axis=1)
        sums_to_one = np.isclose(probabilities.sum(axis=1), 1.0, rtol=0.0, atol=1e-10)
        invalid = ~(finite & in_unit_interval & sums_to_one)
        if invalid.any():
            raise DataValidationError([
                f"{label} H/D/A probabilities must be finite, lie in [0, 1], and sum to 1 within 1e-10; "
                f"invalid prediction CSV row(s): {_prediction_csv_rows(invalid)}"
            ])
        prediction.loc[:, columns] = probabilities


def _metric_summary(scored: pd.DataFrame) -> dict:
    """Return identically named score metrics for an explicitly stated population."""
    return {
        "rows_scored": int(len(scored)),
        "M0_mean_Brier_unscaled": float(scored["M0_Brier_unscaled"].mean()) if len(scored) else None,
        "M1_mean_Brier_unscaled": float(scored["M1_Brier_unscaled"].mean()) if len(scored) else None,
        "M0_mean_RPS": float(scored["M0_RPS"].mean()) if len(scored) else None,
        "M1_mean_RPS": float(scored["M1_RPS"].mean()) if len(scored) else None,
    }


def score_live_predictions(predictions_path: str | Path, data: str | Path, output_dir: str | Path) -> dict:
    """Score an immutable prediction CSV against completed results available now."""
    predictions_path, output_dir = Path(predictions_path), Path(output_dir)
    prediction = pd.read_csv(predictions_path)
    needed = {
        "Date", "HomeTeam", "AwayTeam", "M1_H", "M1_D", "M1_A", "M0_H", "M0_D", "M0_A",
        "created_at_utc", "as_of", "latest_training_date",
    }
    missing = sorted(needed - set(prediction.columns))
    if missing:
        raise DataValidationError([f"prediction log missing required column(s): {', '.join(missing)}"])
    if prediction.empty:
        raise DataValidationError(["prediction log contains no rows"])
    for column in ("HomeTeam", "AwayTeam"):
        prediction[column] = prediction[column].fillna("").astype(str).str.strip()
    invalid_identity = (prediction[["HomeTeam", "AwayTeam"]] == "").any(axis=1)
    if invalid_identity.any():
        raise DataValidationError([f"prediction log requires nonblank HomeTeam and AwayTeam; CSV row(s): {_prediction_csv_rows(invalid_identity)}"])
    if (prediction["HomeTeam"] == prediction["AwayTeam"]).any():
        raise DataValidationError(["a prediction log fixture cannot name the same team home and away"])
    prediction["Date"] = _parse_log_dates(prediction, "Date")
    if prediction.duplicated(["Date", "HomeTeam", "AwayTeam"], keep=False).any():
        raise DataValidationError(["duplicate Date/HomeTeam/AwayTeam fixture rows in prediction log"])
    prediction["as_of"] = _parse_log_dates(prediction, "as_of")
    prediction["latest_training_date"] = _parse_log_dates(prediction, "latest_training_date")
    prediction["created_at_utc"] = _parse_log_utc_timestamps(prediction["created_at_utc"])
    future_as_of = prediction["as_of"].dt.date > prediction["created_at_utc"].dt.date
    if future_as_of.any():
        raise DataValidationError([
            "as_of cannot be after the actual UTC creation day; "
            f"invalid prediction CSV row(s): {_prediction_csv_rows(future_as_of)}"
        ])
    invalid_fixture_chronology = prediction["Date"] <= prediction["as_of"]
    if invalid_fixture_chronology.any():
        raise DataValidationError([
            "fixture Date must be strictly after as_of; "
            f"invalid prediction CSV row(s): {_prediction_csv_rows(invalid_fixture_chronology)}"
        ])
    invalid_training_chronology = prediction["latest_training_date"] >= prediction["as_of"]
    if invalid_training_chronology.any():
        raise DataValidationError([
            "latest_training_date must be strictly before as_of; "
            f"invalid prediction CSV row(s): {_prediction_csv_rows(invalid_training_chronology)}"
        ])
    _validate_prediction_probabilities(prediction)

    recomputed_prospective = (
        (prediction["Date"] > prediction["as_of"])
        & (prediction["latest_training_date"] < prediction["as_of"])
        & (prediction["as_of"].dt.date <= prediction["created_at_utc"].dt.date)
        & (prediction["created_at_utc"].dt.date < prediction["Date"].dt.date)
    )
    if "prospective_status" in prediction.columns:
        prediction["logged_prospective_status"] = prediction["prospective_status"].fillna("").astype(str)
    else:
        prediction["logged_prospective_status"] = ""
    prediction["prospective_status"] = np.where(recomputed_prospective, "genuinely_prospective", "retrospective")
    status_mismatch = (prediction["logged_prospective_status"] != "") & (prediction["logged_prospective_status"] != prediction["prospective_status"])

    matches, _ = load_matches(data, mode="partial")
    actual = matches[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]]
    merged = prediction.merge(actual, how="left", on=["Date", "HomeTeam", "AwayTeam"], validate="one_to_one")
    scored = merged.loc[merged["FTR"].notna()].copy()
    unscored = merged.loc[merged["FTR"].isna()].copy()
    if not scored.empty:
        actual_onehot = one_hot(scored["FTR"])
        for label in ("M0", "M1"):
            probs = scored[[f"{label}_H", f"{label}_D", f"{label}_A"]].to_numpy(float)
            scored[f"{label}_Brier_unscaled"] = brier_losses(probs, actual_onehot)
            scored[f"{label}_RPS"] = rps_losses(probs, actual_onehot)
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    identifier = now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex[:8]
    detail_path = output_dir / f"live_score_{identifier}.csv"
    unscored_path = output_dir / f"live_unscored_{identifier}.csv"
    summary_path = output_dir / f"live_score_{identifier}.json"
    if detail_path.exists() or unscored_path.exists() or summary_path.exists():
        raise FileExistsError("immutable live score collision; rerun to create a new timestamped log")
    scored.to_csv(detail_path, index=False)
    unscored.to_csv(unscored_path, index=False)
    all_scored_metrics = _metric_summary(scored)
    prospective_metrics = _metric_summary(scored.loc[scored["prospective_status"] == "genuinely_prospective"])
    summary = {
        "type": "immutable_live_score",
        "scored_at_utc": now.isoformat(),
        "prediction_log": str(predictions_path),
        "prediction_log_sha256": sha256(predictions_path),
        "rows_logged": int(len(prediction)),
        "rows_with_actual_results": int(len(scored)),
        "rows_unscored": int(len(prediction) - len(scored)),
        "rows_unscored_or_postponed_no_completed_result": int(len(unscored)),
        "rows_past_fixture_date_without_completed_result": int((unscored["Date"].dt.date < now.date()).sum()),
        "rows_not_yet_due_without_completed_result": int((unscored["Date"].dt.date >= now.date()).sum()),
        "genuinely_prospective_rows_scored": int((scored["prospective_status"] == "genuinely_prospective").sum()),
        "retrospective_rows_scored": int((scored["prospective_status"] != "genuinely_prospective").sum()),
        "genuinely_prospective_rows_logged": int(recomputed_prospective.sum()),
        "retrospective_rows_logged": int((~recomputed_prospective).sum()),
        "logged_prospective_status_mismatch_rows": int(status_mismatch.sum()),
        "metric_population": "all_scored_including_retrospective",
        "all_scored_including_retrospective": all_scored_metrics,
        "prospective_only": prospective_metrics,
        "M0_mean_Brier_unscaled": all_scored_metrics["M0_mean_Brier_unscaled"],
        "M1_mean_Brier_unscaled": all_scored_metrics["M1_mean_Brier_unscaled"],
        "M0_mean_RPS": all_scored_metrics["M0_mean_RPS"],
        "M1_mean_RPS": all_scored_metrics["M1_mean_RPS"],
        "prospective_criterion": "fixture Date > as_of; latest_training_date < as_of; as_of is no later than the UTC creation day; and UTC creation day < fixture Date",
        "interpretation": "Root metric names describe all scored rows, including retrospective rows. prospective_only is calculated only after recomputing the criterion from immutable timestamps and chronology, never from a claimed status label.",
        "detail_csv": str(detail_path),
        "unscored_detail_csv": str(unscored_path),
    }
    write_json(summary_path, summary)
    return {"summary": str(summary_path), "detail": str(detail_path), **summary}
