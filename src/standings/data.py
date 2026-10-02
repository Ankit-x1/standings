"""Input validation and deterministic standings reconstruction.

The loader accepts football-data.co.uk-style result files.  It deliberately uses
only Date, HomeTeam, AwayTeam, FTHG, FTAG, and FTR for the core analysis.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Literal

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR")


class DataValidationError(ValueError):
    """Raised when a result file does not meet the documented schema."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("Data validation failed:\n- " + "\n- ".join(messages))


@dataclass(frozen=True)
class ValidationSummary:
    mode: str
    rows_read: int
    result_rows: int
    incomplete_rows_excluded: int
    teams: int
    date_min: str | None
    date_max: str | None
    complete_schedule: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.map(_text)
    parsed = pd.to_datetime(text, format="%d/%m/%Y", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y-%m-%d", errors="coerce")
    return parsed


def _integer_goals(series: pd.Series, name: str, errors: list[str]) -> pd.Series:
    text = series.map(_text)
    invalid = ~text.str.fullmatch(r"\d+")
    if invalid.any():
        sample = ", ".join(map(str, (invalid[invalid].index[:5] + 2).tolist()))
        errors.append(f"{name} must be nonnegative base-10 integers; invalid CSV row(s): {sample}")
        return pd.Series(np.zeros(len(text), dtype=int), index=series.index)
    # Regex disallows signs and decimals; conversion is safe after that check.
    return text.astype("int64")


def _validate_basic(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df.empty:
        return ["no completed result rows were found"]
    if (df["HomeTeam"] == df["AwayTeam"]).any():
        errors.append("a team cannot play itself")
    duplicate_fixture_date = df.duplicated(["Date", "HomeTeam", "AwayTeam"], keep=False)
    if duplicate_fixture_date.any():
        errors.append("duplicate Date/HomeTeam/AwayTeam fixture rows")
    duplicate_directed = df.duplicated(["HomeTeam", "AwayTeam"], keep=False)
    if duplicate_directed.any():
        errors.append("duplicate directed home/away fixture rows")
    appearances = pd.concat(
        [df[["Date", "HomeTeam"]].rename(columns={"HomeTeam": "Team"}),
         df[["Date", "AwayTeam"]].rename(columns={"AwayTeam": "Team"})],
        ignore_index=True,
    )
    if appearances.duplicated(["Date", "Team"], keep=False).any():
        errors.append("a team appears in more than one fixture on the same date")
    expected = np.where(df["FTHG"] > df["FTAG"], "H", np.where(df["FTHG"] < df["FTAG"], "A", "D"))
    if not np.array_equal(expected, df["FTR"].to_numpy()):
        errors.append("FTR is inconsistent with FTHG and FTAG")
    return errors


def _complete_schedule_errors(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    teams = sorted(set(df["HomeTeam"]) | set(df["AwayTeam"]))
    n = len(teams)
    expected_matches = n * (n - 1)
    if n != 20:
        errors.append(f"complete mode requires 20 teams, found {n}")
    if len(df) != 380:
        errors.append(f"complete mode requires 380 result rows, found {len(df)}")
    if len(df) != expected_matches:
        errors.append(f"complete directed round robin needs {expected_matches} rows for {n} teams")
    home_counts = df.groupby("HomeTeam").size().reindex(teams, fill_value=0)
    away_counts = df.groupby("AwayTeam").size().reindex(teams, fill_value=0)
    if not (home_counts == n - 1).all() or not (away_counts == n - 1).all():
        errors.append("complete mode requires every team to have exactly 19 home and 19 away matches")
    pairs = set(zip(df["HomeTeam"], df["AwayTeam"]))
    expected_pairs = {(h, a) for h in teams for a in teams if h != a}
    if pairs != expected_pairs:
        errors.append("complete mode requires every ordered pair of distinct teams exactly once")
    return errors


def load_matches(
    path: str | Path,
    mode: Literal["auto", "complete", "partial"] = "auto",
) -> tuple[pd.DataFrame, ValidationSummary]:
    """Load completed matches, enforcing strict score/result consistency.

    ``complete`` requires a 20-team, 380-game double round-robin. ``partial``
    validates completed rows but permits an unfinished season; rows with all
    three result fields blank are explicitly excluded as unplayed fixtures.
    ``auto`` chooses the same validation level as partial but records whether
    the returned rows also satisfy complete mode.
    """
    if mode not in {"auto", "complete", "partial"}:
        raise ValueError("mode must be one of: auto, complete, partial")
    path = Path(path)
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except Exception as exc:  # pragma: no cover - pandas error detail is retained
        raise DataValidationError([f"could not read {path}: {exc}"]) from exc
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing_columns:
        raise DataValidationError([f"missing required column(s): {', '.join(missing_columns)}"])

    errors: list[str] = []
    # Retain provider columns (notably the pre-selected AvgC closing odds) so
    # evaluation can use them, while validation below depends only on the six
    # documented core fields.
    work = raw.copy()
    for column in ("HomeTeam", "AwayTeam"):
        work[column] = work[column].map(_text)
    work["FTR"] = work["FTR"].map(_text).str.upper()
    work["Date"] = _parse_dates(work["Date"])

    missing_identity = work[["Date", "HomeTeam", "AwayTeam"]].isna().any(axis=1) | (work["HomeTeam"] == "") | (work["AwayTeam"] == "")
    if missing_identity.any():
        errors.append("Date, HomeTeam, and AwayTeam are required for every row")

    goal_text = raw[["FTHG", "FTAG", "FTR"]].map(_text)
    all_blank_result = (goal_text == "").all(axis=1)
    any_blank_result = (goal_text == "").any(axis=1)
    partial_result = any_blank_result & ~all_blank_result
    if partial_result.any():
        errors.append("a row has only part of FTHG/FTAG/FTR; use all three values or leave all three blank")
    if mode == "complete" and all_blank_result.any():
        errors.append("complete mode does not permit unplayed fixtures")
    result_mask = ~all_blank_result
    work = work.loc[result_mask].copy()
    raw_results = raw.loc[result_mask]

    if not work.empty:
        work["FTHG"] = _integer_goals(raw_results["FTHG"], "FTHG", errors)
        work["FTAG"] = _integer_goals(raw_results["FTAG"], "FTAG", errors)
        invalid_ftr = ~work["FTR"].isin(["H", "D", "A"])
        if invalid_ftr.any():
            sample = ", ".join(map(str, (invalid_ftr[invalid_ftr].index[:5] + 2).tolist()))
            errors.append(f"FTR must be H, D, or A; invalid CSV row(s): {sample}")
        errors.extend(_validate_basic(work))
    elif not errors:
        errors.append("no completed result rows were found")

    if errors:
        raise DataValidationError(errors)

    work = work.sort_values("Date", kind="stable").reset_index(drop=True)
    complete_errors = _complete_schedule_errors(work)
    complete = not complete_errors
    if mode == "complete" and complete_errors:
        raise DataValidationError(complete_errors)
    warnings: list[str] = []
    if mode == "auto" and not complete:
        warnings.append("partial schedule: complete-season checks were not applied")
    if mode == "partial" and complete:
        warnings.append("file happens to satisfy complete-season checks; partial mode was requested")
    summary = ValidationSummary(
        mode=mode,
        rows_read=len(raw),
        result_rows=len(work),
        incomplete_rows_excluded=int(all_blank_result.sum()),
        teams=len(set(work["HomeTeam"]) | set(work["AwayTeam"])),
        date_min=work["Date"].min().date().isoformat() if not work.empty else None,
        date_max=work["Date"].max().date().isoformat() if not work.empty else None,
        complete_schedule=complete,
        warnings=tuple(warnings),
    )
    return work, summary


def rebuild_standings(matches: pd.DataFrame, teams: list[str] | None = None) -> pd.DataFrame:
    """Rebuild a table from results, sorting points, GD, GF then alphabetically.

    Alphabetical ordering is only a deterministic display fallback for exact
    Pts/GD/GF ties; it is *not* an assertion of official head-to-head rules.
    """
    if teams is None:
        teams = sorted(set(matches["HomeTeam"]) | set(matches["AwayTeam"]))
    table = pd.DataFrame(0, index=pd.Index(sorted(teams), name="Team"), columns=["P", "W", "D", "L", "GF", "GA", "Pts"], dtype="int64")
    for row in matches.itertuples(index=False):
        h, a, hg, ag = row.HomeTeam, row.AwayTeam, int(row.FTHG), int(row.FTAG)
        table.loc[h, ["P", "GF", "GA"]] += [1, hg, ag]
        table.loc[a, ["P", "GF", "GA"]] += [1, ag, hg]
        if hg > ag:
            table.loc[h, ["W", "Pts"]] += [1, 3]
            table.loc[a, "L"] += 1
        elif hg < ag:
            table.loc[a, ["W", "Pts"]] += [1, 3]
            table.loc[h, "L"] += 1
        else:
            table.loc[[h, a], ["D", "Pts"]] += [1, 1]
    table["GD"] = table["GF"] - table["GA"]
    table = table.reset_index()[["Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]]
    table = table.sort_values(["Pts", "GD", "GF", "Team"], ascending=[False, False, False, True], kind="stable").reset_index(drop=True)
    table.insert(0, "Rank", np.arange(1, len(table) + 1))
    return table
