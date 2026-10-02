# Start from scratch — Calling the Table

**For Ankit Karki and the MATH 3315 group**  
Read this after the proposal. The project is an academic Python analysis, not a betting app. You do not need a paid API, a web server, or machine-learning training.

## 1. Understand the first assignment before coding

Part 1 asks for **a group proposal**, not a completed program. The repository's `Proposal Requirements.pdf` asks for five things: team/roles, project plan, written documentation, tools and their uses, and presentation content. `docs/Proposal_Ankit_Karki.pdf` covers all five.

Before submitting:

1. Open the editable Word document or `docs/Proposal.md`.
2. Add the other members' real names; assign Group Lead and Project Planner. **Ankit Karki is QA Lead.** Do not invent names or signatures.
3. Confirm the real Canvas due date. All dates in the proposal are targets, not the assignment deadline.
4. Ask the instructor whether the topic is unclaimed and whether the scope is accepted. A draft message is in `docs/Requirements_Checklist.md`.
5. Complete your group's signed contract separately.
6. Schedule the required proposal review/sign-off meeting.
7. Upload the proposal as one PDF. Each member separately submits a meaningful Peer Evaluation Form concurrently with Part 1; omission means 0 for that student's Part 1 grade.
8. Download the missing **Results Requirements** before deciding that Part 2 is ready.

No Canvas submission, message to your instructor, or signature has been performed automatically.

## 2. What the project does

The full pipeline:

```text
Frozen real match CSV
  -> strict data checks
  -> chronological training-only rates
  -> Poisson scoreline probabilities
  -> match forecasts and Brier/RPS scores
  -> date-block uncertainty and calibration
  -> 10,000 remaining-season simulations
  -> final-points intervals, tables, charts, and QA evidence
```

- **Model 0:** Every fixture uses the league's earlier home/away scoring averages.
- **Model 1:** Earlier venue-specific team scoring/conceding averages scale those league rates.
- **Market benchmark:** Normalized inverse **AvgCH/AvgCD/AvgCA** closing odds. These probabilities are an evaluation benchmark only.
- **Optional Model 2:** Dixon–Coles correction is outside the completed core until deliberately added and tested.

More simulation runs reduce randomness in the simulation output. They do **not** make a poor model correct.

## 3. Install the free tools

Use **Python 3.11 or newer**, [VS Code](https://code.visualstudio.com/), and [Git](https://git-scm.com/downloads). Microsoft Excel is useful but an equivalent spreadsheet program can evaluate the hand-check formulas. [Google Colab](https://colab.research.google.com/) is an optional fallback.

### Windows PowerShell

```powershell
git clone https://github.com/Ankit-x1/standings.git
cd standings
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell blocks activation, you can avoid changing system policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m standings --help
```

Use that full Python path in place of `python` for later commands.

### macOS / Linux

```bash
git clone https://github.com/Ankit-x1/standings.git
cd standings
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Always run the following project commands **from the repository root**. Do not name your own file `numpy.py`, `pandas.py`, or `scipy.py`: it can hide the installed library.

## 4. Put the actual data in the right folder

The public repository intentionally excludes provider raw CSVs. Your privately delivered project ZIP includes the coursework snapshots. If you clone GitHub instead, obtain them manually:

1. Visit [Football-Data's England page](https://www.football-data.co.uk/englandm.php).
2. Under 2025/2026, download **Premier League**.
3. Save the unchanged file as `data/raw/E0_2526.csv`.
4. For the optional live extension, download 2026/2027 as `data/raw/E0_2627.csv`.
5. Read the [provider notice](https://www.football-data.co.uk/data.php) and [column notes](https://www.football-data.co.uk/notes.txt). Use the files for private coursework; do not republish them or run an unattended collection service.

Direct source: [2025/26 CSV](https://www.football-data.co.uk/mmz4281/2526/E0.csv). A downloaded file may initially be named `E0.csv`: rename it to identify its season. Do not confuse it with a current-season file.

The inspected historical snapshot has **380 matches** and **20 teams**. The delivered live snapshot has only **50 matches through September 20, 2026**; it is not a complete-season dataset and should not be fed into complete-season validation.

Important fields:

| Column | Meaning |
| --- | --- |
| Date | Match date, day-first in the provider CSV. |
| HomeTeam / AwayTeam | Provider's team names; keep spelling consistent. |
| FTHG / FTAG | Full-time home and away goals. |
| FTR | Full-time result: H, D, or A. |
| AvgCH / AvgCD / AvgCA | Market-average closing decimal odds for home/draw/away. |

The completed-season file has a UTF-8 byte-order mark; the loader handles it. The core model intentionally ignores match shots, cards, halftime scores, and xG. Same-match statistics would be unavailable before the match and must not leak into a pre-match predictor.

## 5. Run tests before analysis

```bash
python -m pytest -q
python -m standings --help
```

Tests are small checks of code behavior; any artificial fixtures in tests are **unit-test inputs**, not research data. All reported study results must come from the real frozen match CSV.

If a test fails, preserve the error and add an issue entry. Do not delete the test simply to make the screen green.

## 6. Run the complete historical analysis

```bash
python -m standings run \
  --data data/raw/E0_2526.csv \
  --out outputs \
  --seed 3315 \
  --simulations 10000
```

On PowerShell, use the same command on one line:

```powershell
python -m standings run --data data/raw/E0_2526.csv --out outputs --seed 3315 --simulations 10000
```

The first run validates the complete season, then produces the backtest, season forecast, charts, and execution evidence. Inspect the actual file list in `outputs/`; the generated report explains the run and results. Read `outputs/report.md` first, then inspect the underlying CSVs and figures.

To preserve a second run separately:

```bash
python -m standings run --data data/raw/E0_2526.csv --out outputs_repeat --seed 3315 --simulations 10000
```

Use the same input and parameters to compare numerical output. Creation timestamps may differ even when stochastic calculations are identical. If results change unexpectedly, check the data hash, package versions, and settings before suspecting random-number problems.

## 7. Learn the code in this order

1. **Data loader/validator:** Find where dates, goals, duplicates, and result codes are checked. Explain why a partial season must use a different mode.
2. **Model fitting:** Locate league means and the four venue-specific team averages. Confirm that training excludes the match date.
3. **Probability calculation:** Follow the score grid; home win is the lower triangle when rows represent home goals. Locate adaptive tail control.
4. **Scoring:** Follow H/D/A one-hot outcome vectors, unscaled Brier score, and normalized RPS.
5. **Simulation:** Locate the seeded random generator, remaining fixture goals, point allocations, and ranking approximation.
6. **CLI orchestration:** Read the function that turns these pieces into one reproducible run.
7. **Tests:** Match important assertions to the QA test IDs in `qa/Test_Plan.md`.

You should be able to explain every equation used in your presentation. Generated code is an aid, not a substitute for understanding the model.

## 8. Ankit's first QA session

Open `qa/Test_Plan.md` and `qa/Issue_Log.csv`. Then:

1. Run all tests and save the result/commit identifier.
2. Confirm the data hash matches the run metadata.
3. Check exactly 380 matches and one home/away pairing per directed team pair.
4. Open the five worked examples/hand-check inputs. Preserve their training dates and sums/counts.
5. Independently calculate rates in the provided spreadsheet; check differences to three decimals. Spreadsheet formulas alone are not your manual sign-off.
6. For one fixture, calculate a Poisson cell using `=POISSON.DIST(k,lambda,FALSE)` for each team and multiply the two values.
7. Explain why the sum of the initial displayed grid can be below 1; verify the recorded tail and the expanded computational grid.
8. Review the analytic-versus-simulation uncertainty, not just the largest percentage difference.
9. Independently compare the rebuilt full-season table with an authoritative published final table. This remains a separate manual task.
10. Review the charts and report for matching numbers and honest limitations; record your own review decision.

Example formula explanation: home goals are the matrix rows, away goals are columns. Cell `(2,1)` means a 2–1 home win. The expected points for the home team are `3*P(home win)+P(draw)`, not the points attached to the most likely exact score.

## 9. Make a single retrospective fixture prediction

Use the CLI's `predict --help` to confirm all options. For example:

```bash
python -m standings predict --data data/raw/E0_2526.csv --home Arsenal --away Chelsea --as-of 2026-01-01
```

This uses only matches before January 1, 2026. It is a **retrospective model demonstration**, not evidence that the prediction was created before that date.

Team names must match the provider, e.g. `Man City`, `Man United`, and `Nott'm Forest`; do not guess aliases. Quote names that contain spaces.

## 10. Optional 2026/27 live extension

This is **manual, optional, and not scheduled**. A future season forecast log is only meaningful when saved before the fixture is played.

1. Manually acquire the latest completed-results CSV and record its new hash.
2. Obtain actual upcoming fixtures from a reliable source. Save `Date,HomeTeam,AwayTeam` in a separate fixtures CSV. Do not fabricate fixtures.
3. Review `python -m standings live --help` and create an immutable timestamped prediction log using only earlier dates.
4. Preserve the log unchanged. Predictions made after the fixture date are retrospective and must not count as prospective validation.
5. Once independently obtained results are available, use `python -m standings score-live --help` to score the saved predictions.
6. Keep postponed/mismatched fixtures visible. Never rewrite an original forecast after seeing a result.

The supplied 50-result snapshot does not itself provide a full future schedule or already-saved prospective predictions. Do not label its historical rows “unseen live tests.”

## 11. Recommended learning resources

| Resource | What to learn / use |
| --- | --- |
| [Python tutorial](https://docs.python.org/3/tutorial/) | Functions, files, virtual environments, and command-line basics. |
| [pandas getting started](https://pandas.pydata.org/docs/getting_started/index.html) | CSV loading, date parsing, filtering, grouping, and export. |
| [SciPy Poisson](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.poisson.html) | PMF/CDF and interpreting lambda as the expected goal count. |
| [SciPy Skellam](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.skellam.html) | Difference of independent Poisson variables; verify win/draw probabilities. |
| [NumPy Generator.poisson](https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.poisson.html) | Seeded count sampling; array shapes and reproducibility. |
| [matplotlib quick start](https://matplotlib.org/stable/users/explain/quick_start.html) | Labeled figures, axes, legends, and export. |
| [pytest getting started](https://docs.pytest.org/en/stable/getting-started.html) | Automated tests and readable failure evidence. |
| [Maher, 1982](https://doi.org/10.1111/j.1467-9574.1982.tb00782.x) | Original attack/defense football goal modeling background; our ratio model is simplified. |
| [Dixon and Coles, 1997](https://eprints.lancs.ac.uk/id/eprint/19492/) | Optional low-score dependence extension, not automatically part of the core. |

UMAP/ILAP module documents were not present; use them only after your group obtains and reads the actual modules.

## 12. Troubleshooting

| Symptom | What to do |
| --- | --- |
| `No module named standings` | Activate the correct environment and run `python -m pip install -e '.[dev]'` from the repository root. |
| File not found | Check `data/raw/E0_2526.csv`; a GitHub clone excludes raw files by design. |
| 380-match validation fails | You may have downloaded the live/incomplete season. Verify file name, date range, and source. Never force the count. |
| Invalid goals / FTR | Inspect the exact rejected row; retain it as a finding. Do not silently drop it. |
| Data URL / TLS error | Download manually in your browser and preserve the file; do not keep retrying an automated scraper. |
| Slightly different simulated percentages | Compare seed, N, input hash, and dependency versions; ordinary Monte Carlo noise is expected across different seeds. |
| Model 1 is worse | Report that result. Consider limitations or explicitly labeled extensions; do not tune the core on the test set. |
| Official table does not agree | Check aliases, administrative deductions, source season, and fixture completeness before deciding the implementation is wrong. |

## 13. What is finished versus what is yours to finish

The package supplies the proposal draft, runnable core analysis, tests, computed evidence, report/charts, QA templates, and setup instructions. Your group still must supply names/deadlines, personally check the calculations, verify the authoritative table, secure instructor sign-off, follow the missing Part 2 rubric, present the work, and complete individual peer evaluation/reflection. The optional live experiment and Dixon–Coles extension are not prerequisites for the core study.
