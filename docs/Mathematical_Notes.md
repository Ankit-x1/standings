# Mathematical notes — Calling the Table

These notes explain the **implemented core**. Numeric worked fixtures and fitted rates are generated from the real CSV in `outputs/`. They are not a claim that the student has independently verified the work.

## 1. Why a Poisson distribution?

A Poisson random variable takes nonnegative integer values. Its parameter lambda is both its mean and variance:

$$P(X=k)=e^{-\lambda}\lambda^k/k!,\quad k=0,1,2,\ldots,\qquad E[X]=\operatorname{Var}(X)=\lambda.$$

This is a tractable approximation for football goals, not a law of soccer. A literal homogeneous Poisson process would require stronger assumptions about constant scoring intensity and independent increments; those are not established simply by using a Poisson count model. Injuries, match state, red cards, tactics, and team heterogeneity can cause departures from the assumptions.

## 2. Rate estimation from historical data

For a prediction on date $t$, the training set consists only of matches with `Date < t`. Compute

$$\mu_H=\frac{\text{total training home goals}}{\text{number of training matches}},\quad \mu_A=\frac{\text{total training away goals}}{\text{number of training matches}}.$$

Model 0 uses these two league rates for every fixture. Model 1 uses home and away strengths separately:

- Home attack ratio: home team's earlier home scoring mean divided by $\mu_H$.
- Away defensive-concession ratio: away team's earlier away conceding mean divided by $\mu_H$.
- Away attack ratio: away team's earlier away scoring mean divided by $\mu_A$.
- Home defensive-concession ratio: home team's earlier home conceding mean divided by $\mu_A$.

Multiplying the appropriate ratios and baseline yields

$$\lambda_H=s_H(h)c_A(a)/\mu_H,\qquad \lambda_A=s_A(a)c_H(h)/\mu_A.$$

A conceding ratio above 1 means more goals conceded, not stronger defense. This is a method-of-moments ratio model, not a maximum-likelihood regression fit. Venue-specific histories are small; any shrinkage extension must be explicitly distinguished from the core model. Missing histories use the matching training-set league average. Zero-rate and empty-training conditions need explicit handling.

## 3. From scores to outcomes

Assuming independent home and away goals conditional on fitted rates,

$$g_{ij}=P(X=i,Y=j)=\frac{e^{-\lambda_H}\lambda_H^i}{i!}\frac{e^{-\lambda_A}\lambda_A^j}{j!}.$$

Rows represent home goals, columns away goals. Therefore

$$p_H=\sum_{i>j}g_{ij},\qquad p_D=\sum_{i=j}g_{ij},\qquad p_A=\sum_{i<j}g_{ij}.$$

The lower triangle is a home win. The diagonal is a draw. For a truncation at $K$, the missing probability is

$$\epsilon=1-F_{\mathrm{Pois}(\lambda_H)}(K)F_{\mathrm{Pois}(\lambda_A)}(K).$$

The code expands the grid from its initial 0–10 range until the omitted mass is below $10^{-8}$; probabilities are normalized afterward. Save both $K$ and epsilon so a reviewer can see that normalization did not conceal a large tail. For positive rates, $X-Y$ follows a Skellam distribution, providing a second route to the outcome probabilities. When either rate is zero, explicit degenerate formulas avoid undefined library behavior.

The expected home points are $3p_H+p_D$; expected away points are $3p_A+p_D$. A most-likely exact score is not a substitute for this distribution.

## 4. Scoring probabilistic predictions

Let $p=(p_H,p_D,p_A)$ and let $y$ be the one-hot vector for the observed result.

**Brier score:**

$$\mathrm{BS}=\sum_{c=1}^{3}(p_c-y_c)^2.$$

We do not divide this by three or two. Its range is 0–2; lower is better. A perfect forecast scores 0. Always state the convention when comparing another source's numbers.

**Ranked probability score:** Using the ordinal sequence H, D, A,

$$\mathrm{RPS}=\frac{1}{2}\sum_{j=1}^{2}\left(\sum_{c=1}^{j}p_c-\sum_{c=1}^{j}y_c\right)^2.$$

RPS distinguishes an adjacent-outcome error from a home-versus-away error. Reversing the entire order is equivalent; arbitrary reordering is not.

**Market reference:** For decimal odds $o_c>1$,

$$p_c^{\mathrm{market}}=\frac{1/o_c}{\sum_j1/o_j}.$$

This proportional de-margining is a simple transformation, not proof that market probabilities are unbiased. It does not model favorite–longshot bias. Require a valid whole triplet and compare models on the same eligible matches. Market averages exclude Pinnacle under the current provider policy. Closing odds also reflect later information than the goals-only forecasts.

For paired differences, define $d_t=\mathrm{BS}_0-\mathrm{BS}_1$. A positive mean favors Model 1. Bootstrap dates, retaining every paired observation within a selected date block, and report a percentile interval. A confidence interval crossing zero is insufficient evidence of a difference; it is not evidence that models are identical.

## 5. Monte Carlo match and season simulation

For each fixture draw $X_n\sim\mathrm{Pois}(\lambda_H)$ and $Y_n\sim\mathrm{Pois}(\lambda_A)$. The home-win frequency is the mean of the indicator $I(X_n>Y_n)$. Its sampling standard error is approximately

$$\mathrm{SE}=\sqrt{p_H(1-p_H)/N}.$$

Similar formulas hold for draw and away win. Use analytic probabilities for the diagnostic standard error. A three-SE discrepancy can occur by chance, especially over many comparisons; investigate it rather than automatically deleting the seed or treating it as a deterministic failure.

For the season backtest, fit only at the first full-date boundary at/after 190 results and keep rates fixed. For every remaining pairing, draw goals and add 3/1/0 points to the existing table. Repeat 10,000 seasons, then obtain per-team mean points and 5th/95th percentiles.

Rank by points, goal difference, and goals scored. Shared weights at still-unresolved ties are an explicit approximation. Top-four probability is **top-four finishing probability**, not guaranteed Champions League qualification under every regulation. The known future pairings are used retrospectively; actual future goals are never used in fitting.

These intervals describe **conditional simulation uncertainty given the fitted rates**. They omit rate-estimation uncertainty and structural model uncertainty; narrow intervals can be misleading. Correlated team totals mean the observed fraction inside intervals is descriptive, not twenty independent calibration trials.

## 6. Calibration and goodness of fit

Calibration groups predicted probabilities into bins and compares their average with observed outcome frequencies. Report each bin's sample size; tiny bins cannot support strong conclusions.

A Poisson goal-count fit diagnostic compares observed 0/1/2/3/4+ counts to expected counts. Team-level samples are small, especially at high goal counts. Pool sparse bins and account for an estimated lambda, for example through a parametric bootstrap that refits lambda in each generated sample. These simulated samples are **statistical reference distributions**, not substitute research datasets. Goodness of fit to a marginal distribution does not establish goal independence or out-of-sample predictive skill.

## 7. How to discuss a negative result

If team strengths do not improve Brier/RPS, say so and examine small sample sizes, unregularized ratios, changing strength, or model assumptions. Do not tune on the evaluated future results and then report the same sample as an untouched test. An extension needs its own training-only fitting and a clearly labeled comparison.

A successful course project demonstrates sound modeling, honest validation, reproducibility, and error analysis—not a guaranteed prediction of the champion.

## Sources

[Football-Data notes](https://www.football-data.co.uk/notes.txt), [Maher (1982)](https://doi.org/10.1111/j.1467-9574.1982.tb00782.x), [Dixon–Coles (1997)](https://eprints.lancs.ac.uk/id/eprint/19492/), [SciPy Poisson](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.poisson.html), and [SciPy Skellam](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.skellam.html).
