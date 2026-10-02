# Calling the Table
## A Poisson–Monte Carlo Model of the Premier League

**MATH 3315 · Semester Project · Part 1: Group Proposal**  
**Prepared for:** Course instructor / Business Customer — name to be confirmed  
**Quality Assurance Lead:** Ankit Karki  
**Draft date:** October 2, 2026  
**Primary study:** Completed 2025/26 Premier League season  
**Optional extension:** Prospective predictions during 2026/27

> **Group-review draft.** The mathematical scope and deliverables are defined below. Before submission, enter all team members’ names, the instructor’s name, the Canvas due date, and confirmed meeting and presentation dates. Instructor approval and individual Peer Evaluation Forms are still required; this document does not represent sign-off.

## 1. The team and its roles

Our group proposes an original mathematical modeling project that uses real Premier League results to estimate match-outcome probabilities and simulate final league standings. The official roles below follow the repository’s **Group Roles.pdf**. All members will contribute to the written report, understand the calculations, and participate in the class presentation.

| Member | Required role | Accountability and planned work |
| --- | --- | --- |
| **[Enter member name]** | **Group Lead** | Keep the group focused and participating; complete the signed group contract; coordinate with the instructor; ensure group behavior and accountability procedures are followed. |
| **[Enter member name]** | **Project Planner** | Own and update the schedule, task assignments, progress tracking, and change log; coordinate deadlines with the Lead. Also coordinate data preparation and implementation, with tasks shared across the group. |
| **Ankit Karki** | **Quality Assurance Lead** | Own the test plan and recorded results; verify calculations, probabilities, simulations, graphs, documentation, and presentation; maintain the issue log; confirm that deliverables meet the instructor-approved requirements. |
| **[Enter additional members, if applicable]** | Supporting responsibilities | Assist with derivations, data checks, code, literature review, writing, and presentation. |

The course requires a group of **three to five students**. A member may fill more than one role, but Lead, Project Planner, and QA Lead must all be assigned. The completed signed group contract is a **separate PDF deliverable**.

## 2. High-level project plan

### Problem and research question

Goals in soccer matches are nonnegative counts with substantial randomness. A model’s expected number of goals is a rate parameter, not a certain score. We will turn estimated goal rates into a distribution of scorelines, then into match-outcome and final-points probabilities.

**Primary question:** Does a transparent team-specific attack/defense model improve probabilistic forecasts over a league-average Poisson model in an honest walk-forward backtest?

**Secondary questions:** How do the models compare with normalized market-average closing-odds probabilities, and how well do midseason simulations describe the eventual final points totals? The benchmark is used for model evaluation only, not for betting or financial advice. We will report unfavorable results as well as favorable ones; improvement is a research hypothesis, not a promised outcome.

### Scope and verified feasibility

The core dataset is the public **2025/26 Premier League results CSV** from football-data.co.uk [1–3]. A feasibility inspection on October 2, 2026 found **380 match records, 20 home-team names, and dates from August 15, 2025 through May 24, 2026**. Full-season average goals were **1.5263 for home teams** and **1.2237 for away teams**. These whole-season averages are descriptive feasibility statistics only; they will **not** be supplied to earlier-date predictions.

The core fields are `Date`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, and `FTR`. The market benchmark will use the fixed triplet `AvgCH`, `AvgCD`, and `AvgCA`, subject to valid values. The provider warns that Pinnacle odds have been systematically stale since July 23, 2025 and are excluded from its market averages [1]. We therefore will not use the pasted draft’s `PSCH/PSCD/PSCA` benchmark.

The 2026/27 URL is available; the inspected snapshot contains **50 completed matches through September 20, 2026**. This extension depends on obtaining future fixtures and retaining predictions before the fixtures are played. Existing results are retrospective evidence, not a live prediction test. The core project does not depend on the extension succeeding. Although the live snapshot contains `HxG` and `AxG`, expected-goals covariates and shots remain **outside the core scope** to keep both seasons’ methodology consistent.

We will freeze source files locally, record retrieval information and SHA-256 hashes, and attribute the provider. Its stated restrictions on commercial/data-training use and automated collection will be respected; no unattended scraper or commercial product is proposed. Raw provider files will not be republished in the public GitHub repository.

### Mathematical approach

Let home goals be $X$ and away goals be $Y$. Under the core model,

$$X\sim\mathrm{Poisson}(\lambda_H),\qquad Y\sim\mathrm{Poisson}(\lambda_A),\qquad P(X=k)=\frac{e^{-\lambda_H}\lambda_H^k}{k!}.$$

Assuming conditional independence,

$$P(X=i,Y=j)=P(X=i)P(Y=j).$$

Summing below, on, and above the scoreline matrix diagonal gives home-win, draw, and away-win probabilities. A $0$–$10$ grid will be the initial display. The computational grid will expand until its omitted probability mass is below $10^{-8}$, then the retained probabilities will be normalized. This avoids assuming that a fixed grid always captures enough mass.

**Model 0 — league-average baseline.** From matches dated strictly before the prediction date, estimate the league home and away goal means $\mu_H$ and $\mu_A$. Set $\lambda_H=\mu_H$ and $\lambda_A=\mu_A$ for every fixture.

**Model 1 — team-strength ratio model.** For home team $h$ and away team $a$, let $s_H(h)$ be the home team’s home scoring mean; $c_A(a)$ the away team’s away conceding mean; $s_A(a)$ the away team’s away scoring mean; and $c_H(h)$ the home team’s home conceding mean. Then

$$\lambda_H=\frac{s_H(h)}{\mu_H}\frac{c_A(a)}{\mu_H}\mu_H,\qquad \lambda_A=\frac{s_A(a)}{\mu_A}\frac{c_H(h)}{\mu_A}\mu_A.$$

Missing venue-specific team histories will fall back to the corresponding training-set league mean. Zero and missing-history cases will be explicitly tested. This is a simple method-of-moments ratio model inspired by attack/defense Poisson modeling [4], not a claim to reproduce Maher’s full fitted model. Any shrinkage modification must be documented and evaluated separately rather than silently changing Model 1.

**Optional Model 2.** If core work is complete, investigate a fitted Dixon–Coles low-score dependence correction [5]. It is a stretch goal, not a required core deliverable, and any fitted parameter must use training data only.

### Backtesting and season simulation

**Walk-forward validation:** Reserve an initial warm-up of at least 100 matches. Start evaluation on the next eligible full date, and fit each prediction only on rows with `Date < prediction date`. All matches on one date therefore share the same available historical information. The evaluated count may differ slightly from 280 if the warm-up boundary falls within a date batch; the count and dates will be reported.

Use outcome order **home win, draw, away win**. Report the unscaled three-outcome Brier score, $\sum_{c=1}^{3}(p_c-y_c)^2$, and the normalized ranked probability score, $\frac12\sum_{j=1}^{2}(\sum_{c=1}^{j}p_c-\sum_{c=1}^{j}y_c)^2$. Lower scores are better. Convert decimal odds to probabilities using $p_c=(1/o_c)/\sum_j(1/o_j)$. Market comparisons use the same matches with valid complete odds triplets and report excluded rows. Closing odds contain information nearer kickoff than the historical goals-only model, so this is a contextual benchmark, not an equal-information experiment.

Paired **date-block bootstrap** intervals will summarize uncertainty in score differences while preserving same-date dependence. Calibration plots will show predicted versus observed outcome frequencies, including bin counts.

**Midseason table backtest:** Select the first complete date boundary at or after 190 played matches; report the exact cutoff, which is not necessarily official round 19. Fit Model 1 on those played matches and freeze its parameters. Simulate only the remaining home/away pairings, without using their actual goals or results, in at least **10,000 seasons**. Add simulated points to existing points and summarize final-points means and 90% intervals. Standings use points, goal difference, and goals scored; any unresolved equality will be reported with an explicit tie approximation, not misrepresented as the official tie-break procedure. Administrative points deductions or exceptional regulations require separate checks.

### Milestones and responsibilities

The following dates are **proposed planning targets**, not Canvas deadlines. The Project Planner will replace them if the instructor’s dates differ.

| Target window | Milestone / evidence | Accountable role |
| --- | --- | --- |
| Oct 2–9 | Confirm topic is unclaimed; fill roles; signed contract; confirm Canvas deadline; schedule proposal review and sign-off; obtain Results Requirements. | Lead and Planner |
| Oct 10–23 | Freeze and validate data; complete model derivations, Models 0/1, adaptive scoreline grid, and five hand-check calculations. | Planner; QA review by Ankit |
| Oct 24–Nov 6 | Complete match and season simulations, seed/reproducibility tests, walk-forward predictions, and scored comparisons. | Planner and Ankit |
| Nov 7–13 | Produce table backtest, calibration, first written results draft, and **first presentation draft by Nov 13**. | All members |
| Nov 14–20 | Review possible sources of error; resolve issues; verify tables/graphs and proposed presentation content. | Ankit; all members assist |
| Nov 21–Dec 1 | Buffer around Thanksgiving on Nov 26; optional prospective forecast log / Model 2 only if core is complete; final QA and rehearsal. | Planner and Ankit |
| **Dec 2, 2026 — proposed** | Class presentation, subject to instructor approval; submit results on the confirmed Canvas date. | Lead and all presenters |

The Planner will check UTA’s course/academic calendar, exam dates, other group commitments, and actual school closures before locking this plan. Scope changes will be communicated promptly to the Business Customer and negotiated before deliverables change.

### Quality assurance and possible sources of error

Ankit Karki will maintain a dated test plan and issue log. Implementation correctness is distinct from model predictive performance: a weak but correctly implemented model must be reported honestly, not altered after seeing results to manufacture a pass.

| QA activity | Acceptance criterion / interpretation |
| --- | --- |
| Data integrity | Completed season has 380 rows and 20 teams; every directed home/away pairing occurs once; each team has 19 home and 19 away fixtures; no duplicate match keys; dates and nonnegative integer goals are valid; goals agree with `FTR`. |
| Rebuilt standings | Verify matches, points, goals for/against, and goal difference; independently compare to an authoritative final table. Record any deductions or naming differences. This external check is not satisfied merely by rebuilding the same CSV. |
| Five hand checks | Independently recompute Model 1 rates and selected Poisson probabilities in Excel; agreement to three decimal places, with the training cutoff and inputs preserved. |
| Probability checks | Values finite and nonnegative; normalized outcome probabilities sum to 1 within $10^{-12}$; omitted grid mass below $10^{-8}$; compare with a Skellam/degenerate-case calculation. |
| Leakage prevention | Every training date is strictly earlier than the predicted match date; changing later results cannot alter earlier predictions. |
| Simulation checks | Fixed seeds reproduce results; points follow 3/1/0 scoring; simulated probabilities are compared with analytic values using standard errors. A three-standard-error discrepancy is investigated as a stochastic diagnostic, not treated as proof of a bug. |
| Stability | Report estimates at 1,000, 5,000, 10,000, and 100,000 match simulations with Monte Carlo uncertainty; do not demand monotonic convergence. |
| Predictive evaluation | Report Brier/RPS scores, valid-market sample size, paired intervals, and calibration without promising Model 1 outperforms Model 0 or the market. |
| Distribution / interval assessment | Exploratory Poisson goodness-of-fit uses sparse-bin pooling and accounts for fitted rates; report 90% points-interval coverage descriptively. Twenty correlated team totals do not establish exact 90% calibration. |
| Deliverable review | Derivations, examples, tables, graphs, report, and presentation agree with reproducible outputs; unresolved limitations and human approvals are clearly identified. |

Main error sources are sparse team histories, changing team strength, dependence between goals, rate-estimation uncertainty, omitted injuries/lineups/red cards, date-only availability, data-source errors, missing odds, and simplified tie handling. More simulations reduce sampling noise but do not repair incorrect assumptions.

## 3. Written documentation to be delivered

The group will deliver:

- A mathematical explanation of the Poisson assumption, both core models, scoreline aggregation, 3/1/0 points, and Monte Carlo procedure.
- Five worked numerical examples with independent spreadsheet checks and documented training cutoffs.
- A data dictionary, source/provenance record, validation findings, and fitted team-rate tables.
- A selected match’s scoreline matrix and analytic-versus-simulation comparison.
- Walk-forward prediction and score tables, paired bootstrap intervals, and calibration plots.
- Midseason forecast-versus-actual points table, uncertainty intervals, and a discussion of successes, failures, and limitations.
- A reproducible code package, setup/run instructions, test evidence, Ankit’s QA plan, dated issue log, and requirements checklist.

The final Part 2 format will be reconciled with the **Results Requirements** document once the group obtains it. That document is not currently in the repository. Individual reflection and peer evaluation must be completed personally by each student.

## 4. Computational / technology tools

| Tool | Use |
| --- | --- |
| Python 3.11+ | Reproducible command-line pipeline and model implementation. |
| pandas | CSV parsing, date filtering, grouped historical means, data validation, and table reconstruction. |
| NumPy | Seeded Poisson sampling, array operations, season simulations, and bootstrap sampling. |
| SciPy | Poisson probability functions, goal-difference cross-checks, and exploratory statistical diagnostics. |
| matplotlib | Scoreline, calibration, score-comparison, goal-count, and points-interval graphs. |
| Excel or compatible spreadsheet | Independent hand calculations, milestone tracking, and QA evidence review. |
| GitHub: Ankit-x1/standings | Shared code, documentation, issue tracking, version history, and automated unit tests. No raw-data republication. |
| VS Code / optional Google Colab | Local development or a browser-based fallback, using the same frozen inputs and commands. |

## 5. Proposed class presentation

We will open with: **“Can a simple goals-only model describe the final Premier League table, and how uncertain should its predictions be?”**

The presentation will cover the research question, real data and chronological cutoff, Poisson derivation, a worked fixture, model comparisons, simulated final-points intervals versus actual points, QA evidence, and limitations. It will distinguish retrospective evaluation from any genuinely prospective 2026/27 predictions. Each member will explain their contribution; Ankit will present verification evidence and error analysis. Duration and final date will be confirmed with the instructor.

### Submission and sign-off checklist

- Fill all names and confirm three to five group members; complete the separate signed group contract.
- Confirm that no other group has this topic and that the original-project scope is acceptable.
- Confirm the Canvas Part 1 due date/time; upload the group proposal as **one PDF**.
- Each student separately submits a serious, meaningful **Peer Evaluation Form concurrently with Part 1**. The course documents state that missing it results in **0 for that student’s Part 1 grade**.
- Schedule the Business Customer meeting and obtain sign-off to proceed.
- Obtain Part 2 Results Requirements; confirm presentation date, duration, and final deliverables.

### References

[1] Football-Data.co.uk. [Data description, availability, usage conditions, and Pinnacle warning](https://www.football-data.co.uk/data.php). Accessed October 2, 2026.

[2] Football-Data.co.uk. [England datasets](https://www.football-data.co.uk/englandm.php); [2025/26 Premier League CSV](https://www.football-data.co.uk/mmz4281/2526/E0.csv); [2026/27 Premier League CSV](https://www.football-data.co.uk/mmz4281/2627/E0.csv). Accessed October 2, 2026.

[3] Football-Data.co.uk. [Column definitions and source acknowledgements](https://www.football-data.co.uk/notes.txt). Accessed October 2, 2026.

[4] Maher, M. J. (1982). “Modelling association football scores.” *Statistica Neerlandica*, 36(3), 109–118. [DOI: 10.1111/j.1467-9574.1982.tb00782.x](https://doi.org/10.1111/j.1467-9574.1982.tb00782.x).

[5] Dixon, M. J., and Coles, S. G. (1997). “Modelling association football scores and inefficiencies in the football betting market.” *Journal of the Royal Statistical Society: Series C (Applied Statistics)*, 46(2), 265–280. [University repository citation](https://eprints.lancs.ac.uk/id/eprint/19492/).

Course requirements: *Math_3315_SP-Overview.pdf*, *Proposal Requirements.pdf*, and *Group Roles.pdf*, supplied in the standings repository. UMAP/ILAP module files were not supplied; no unverified module contents are claimed.
