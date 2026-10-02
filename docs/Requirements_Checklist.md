# Requirements checklist and repository audit

**Audit date:** October 2, 2026  
**Student / QA Lead:** Ankit Karki

## Sources actually reviewed

The original repository contained exactly four project files, plus Git metadata:

| Source | Contents reviewed |
| --- | --- |
| `Math_3315_SP-Overview.pdf` | Two pages: high-level modeling/communication/verification goals; groups of 3–5; unique topic requirement; instructor alignment; contract, Part 1, Part 2, individual peer evaluation and reflection. |
| `Proposal Requirements.pdf` | Two pages: five proposal components, PDF upload, Business Customer meeting/sign-off, concurrent individual peer evaluations, prompt communication of significant changes. |
| `Group Roles.pdf` | One page: accountable versus responsible; mandatory Lead, Project Planner, QA Lead; one member may fill multiple roles. |
| `README.md` | Only the heading `# math_r`; no pre-existing implementation. |
| User attachment `pasted_content.txt` | The full prior Claude conversation: Premier League choice, draft proposal, example code, QA plan, and setup suggestions. |

**Not present:** Results Requirements, signed contract, Peer Evaluation Form/template, reflection instructions, UMAP/ILAP module PDFs, team roster, instructor name, Canvas deadlines, presentation time limit. The external Canvas links were not needed to retrieve the three already-supplied requirement PDFs. No claim is made to have accessed the user's Canvas account.

## Part 1: exact five requested components

| Requirement | Where addressed | Remaining action |
| --- | --- | --- |
| The Team | Proposal section 1; Ankit Karki explicitly QA Lead. | Add all member names and confirm 3–5 members; assign Lead and Planner. |
| High-Level Project Plan | Proposal section 2: scope, models, milestones, Nov 13 presentation draft, QA, errors, Thanksgiving buffer, proposed Dec 2 presentation. | Confirm course deadlines and UTA/class events; negotiate dates with instructor. |
| Written Documentation | Proposal section 3: derivations, solved examples, data/provenance, graphs, validation tables, QA, reproducible code. | Reconcile with Part 2 Results Requirements. |
| Computational/Technology Tools | Proposal section 4: each tool and its purpose. | Group verifies everyone can run it and explain the code. |
| Presentation | Proposal section 5: question, derivation, worked fixture, forecast, validation, QA, limitations. | Confirm presentation duration/date; add missing team names. |

## Requirements outside the proposal itself

- [ ] Group Lead confirms that this project topic is not claimed by another group.
- [ ] Group completes and signs its own group contract; uploads a separate PDF as directed.
- [ ] Group uploads one proposal PDF to Canvas by its actual deadline. Pasted assignment says 11:59 PM CST; verify the Canvas-displayed date/time rather than assuming a date.
- [ ] Every member individually submits a meaningful Peer Evaluation Form concurrently with Part 1. Missing it gives that student **0 for Part 1**, per the course PDFs.
- [ ] Group schedules the Business Customer meeting and obtains instructor sign-off.
- [ ] Planner obtains Results Requirements and updates the agreed final deliverables.
- [ ] Group coordinates the final class presentation with the instructor.
- [ ] Every student writes their own individual reflection using actual experiences.

The user attachment states Part 1 is **30 of 100 semester-project points** and the semester project is **15% of the course grade**. These grading values come from the pasted assignment, not an independently opened current Canvas page.

## Important corrections to the pasted Claude plan

1. **Data availability verified:** 2025/26 has 380 results; 2026/27 snapshot has 50 results. These are different validation modes.
2. **Market benchmark changed:** AvgCH/AvgCD/AvgCA, not stale Pinnacle PSCH/PSCD/PSCA.
3. **Adaptive tail control:** a fixed grid need not sum to 1; rates can produce larger tails.
4. **Strict date leakage:** no same-date training; warmup and halfway cutoffs respect full-date batches.
5. **Date-block bootstrap:** uncertainty uses paired scores clustered by date, rather than assuming every match is independent.
6. **Diagnostics are not guarantees:** three-SE deviations, Poisson fit, interval coverage, and model superiority are evidence to interpret.
7. **Season forecast is conditional:** known remaining pairings are used, future results are not; freeze rates and disclose tie approximation/parameter uncertainty.
8. **Live means saved beforehand:** a timestamped file created after a result is known is not a prospective test.
9. **No fictional evidence:** official-table verification, Ankit's hand checks, signatures, team names, and course sign-off remain pending until performed.
10. **No raw public republication:** public repository contains source/provenance and derived outputs, not provider raw CSV copies.

## Instructor scope message — draft for the group to send

> Our group would like to propose “Calling the Table,” an original Poisson–Monte Carlo model of Premier League results. The required core is a 2025/26 chronological backtest comparing a league-average model, a transparent team-strength model, and a market-average closing-odds benchmark, followed by a midseason final-points simulation and documented QA. Ankit Karki will be our QA Lead. A prospective 2026/27 forecast and Dixon–Coles correction are optional extensions. Is this topic unclaimed, and do these deliverables satisfy the project requirements? Could we schedule the required proposal sign-off meeting and confirm the Part 2 rubric and presentation date?

This message has **not** been sent to anyone.
