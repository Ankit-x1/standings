# QA test plan — Ankit Karki

**Project:** Calling the Table, MATH 3315  
**Owner:** Ankit Karki, Quality Assurance Lead  
**Version:** 1.0, October 2, 2026  
**Status:** Initial baseline. Automated evidence is produced by the code; manual review is not signed off by this document.

## Purpose and separation of evidence

Verify that the implementation follows the approved model and that the reported evidence is reproducible. **Correct software can implement a statistically weak model.** A negative predictive result is not a failed assignment; misleading results or leakage are defects.

Statuses: **PASS**, **FAIL**, **PENDING**, **NOT APPLICABLE**, **DIAGNOSTIC**. Never change PENDING to PASS without the specified evidence. The program's generated `outputs/qa_checks.json` is execution evidence, not Ankit's personal signature.

## Test cases

| ID | Check | Procedure / evidence | Acceptance | Type |
| --- | --- | --- | --- | --- |
| D01 | Required schema | Parse UTF-8/BOM CSV and dates; inspect required columns. | Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR available; dates valid; no required missing values in results mode. | Automated |
| D02 | Valid goals | Validate numeric finite integer counts. | Both goal counts are nonnegative integers; invalid/missing values rejected rather than silently removed. | Automated |
| D03 | Result consistency | Derive H/D/A from goals and compare FTR. | Exact agreement for every row. | Automated |
| D04 | Duplicate/self fixtures | Check date+home+away key and home != away. | No duplicates or self matches. | Automated |
| D05 | Complete season structure | Count results, union of teams, venue counts, directed pairs. | 380 matches, 20 teams, 19 home/19 away each, every directed pair once. Partial live file uses a separate validation mode. | Automated |
| D06 | Official final-table reconciliation | Compare independently sourced final P/W/D/L/GF/GA/GD/Pts to rebuilt table; normalize team aliases; investigate deductions. | Exact numerical agreement or documented official adjustments. Preserve source URL and access date. | **Manual; pending until completed** |
| D07 | Input provenance | Record local SHA-256, season, retrieval time/method, source, source notice. | Input hash agrees with run metadata; no invisible refresh; no raw-data republication in public repo. | Automated + manual |
| M01 | Model 0 means | Recalculate historical home/away averages. | Same training-only rates; no complete-season rates used for earlier dates. | Automated |
| M02 | Model 1 rate formulas | Recompute five distinct fixtures in spreadsheet from exported training inputs. | Rate/probability agreement to 0.001; inputs and cutoff stored. | **Manual + automated** |
| M03 | Missing/zero histories | Test unseen team, missing venue history, zero rate, and empty training. | Documented league fallback or explicit error; finite nonnegative rate; zero-rate Poisson handled. | Automated |
| P01 | Probability orientation | Check home > away score cells map to home win; symmetric means give symmetric win probabilities. | Correct H/D/A order. | Automated |
| P02 | Probability mass | Expand grid until retained mass meets tolerance. | Omitted mass < 1e-8; values finite/nonnegative; normalized probabilities sum to 1 within 1e-12. | Automated |
| P03 | Independent analytic check | Compare outcome probabilities with SciPy Skellam and explicit degenerate-rate formulas. | Numerical agreement within configured tolerance accounting for tail. | Automated |
| L01 | Date leakage | Verify latest training date < match date and alter later results in a test. | Earlier predictions unchanged; no same-date result used. | Automated |
| S01 | Match Monte Carlo | Compare simulated outcomes with analytic probabilities using standard errors. | Record N/seed/probabilities/z-scores. Investigate >3-SE discrepancy; do not hide it or assume every random discrepancy is a coding error. | Diagnostic |
| S02 | Seed reproducibility | Repeat calculations using same data/settings/seed. | Identical stochastic arrays/tables in the same pinned environment; timestamps may differ. | Automated |
| S03 | Stability | Compare N=1,000/5,000/10,000/100,000 for one fixture. | Report sampling uncertainty; no requirement of monotonic improvement at every N. | Diagnostic |
| S04 | Points allocation | Check a home win, away win, draw, and season totals. | Winners receive 3, draws give 1 each; every match contributes either 3 or 2 total points. | Automated |
| S05 | Season cutoff | Report first complete date boundary >=190 results. | No split date; future goals never inform rates; all remaining fixtures simulated. | Automated |
| S06 | Standings and ties | Check points/GD/GF sorting, expected ranks, shared boundary weights. | Explicit unresolved-tie approximation; title/top4/relegation weights sum to 1/4/3 under simulation assumptions. | Automated |
| E01 | Scoring | Test perfect and uniform forecasts for Brier/RPS with H,D,A ordering. | Perfect score 0; Brier convention unscaled and RPS convention divided by 2. | Automated |
| E02 | Odds benchmark | Validate fixed AvgCH/AvgCD/AvgCA triplet; normalize inverse odds. | All values finite >1; complete valid triplets only; exclusions reported; common-sample comparisons. Pinnacle not used. | Automated |
| E03 | Bootstrap | Resample date blocks with replacement and preserve paired scores. | 2,000 seeded replicates; interval and sign convention recorded; no sample mismatch. | Automated |
| E04 | Calibration | Preserve bin count and observed outcome frequency. | Graph and data agree; empty/sparse bins not represented as strong evidence. | Automated + visual |
| E05 | Goodness of fit | Pool sparse bins; account for estimated lambda through bootstrap. | Expected-count issues documented; interpretation exploratory, not proof of independence or predictive accuracy. | Diagnostic |
| E06 | Final-points coverage | Count actual totals within 90% intervals. | Report observed coverage and points MAE; do not force exactly 18/20 or treat correlated teams as independent trials. | Diagnostic |
| V01 | Live chronology | Compare creation timestamp with fixture kickoff/date and training cutoff. | Only predictions genuinely saved in advance count as prospective. Retrospective examples must be labeled and excluded. | Automated + manual |
| V02 | Live scoring | Join logs to independently obtained results by fixture identity/date; distinguish postponed matches. | Score only completed matching fixtures; preserve original prediction log; mismatches not silently coerced. | Automated + manual |
| R01 | Reproducible setup | Fresh environment install, tests, CLI run. | Documented commands succeed without secret API keys; dependency versions/run parameters recorded. | Automated |
| R02 | Document/figure consistency | Compare proposal, report, CSV tables, graphs, and slides. | No unsupported improvement claims; all numerical results trace to outputs. | **Manual** |
| R03 | Assignment compliance | Check five Part 1 requirements, separate contract, peer evaluations, instructor sign-off, Part 2 rubric. | All required human tasks complete before group submission. | **Manual** |

## Release criteria

1. All deterministic implementation/data tests pass; unexplained failures block release.
2. Statistical diagnostics are reported, including poor performance or low coverage; they are not erased to obtain a pass.
3. Manual hand checks and external table comparison have recorded reviewers and evidence.
4. No open high-severity data-leakage, scoring, probability, or documentation defect.
5. Member names, due dates, contract, topic uniqueness, peer evaluations, and instructor sign-off are confirmed by the group.

## Ankit's review record

- Reviewer: **Ankit Karki**
- Dataset SHA-256: ____________________
- Commit / run identifier: ____________________
- Manual hand-check evidence: ____________________
- Independent table source and comparison: ____________________
- Open limitations accepted by instructor: ____________________
- Decision: **PENDING personal review**
- Review date / signature: ____________________

No signature, instructor approval, or claim of personally completed work has been fabricated.
