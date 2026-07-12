# YEB — Calculation Decisions Appendix v1.0

**Status:** Binding  
**Version:** 1.0  
**Scope:** Portfolio Confidence Engine and Portfolio Optimizer  

## 1. Purpose and Authority

This appendix defines the binding calculation decisions for YEB portfolio intelligence. It must be read together with documents `01` through `06` in the `docs` directory. If an implementation detail is not defined here, the earlier specifications remain authoritative. If an earlier document leaves a calculation ambiguous, this appendix resolves that ambiguity.

This document covers:

- Portfolio Confidence Index component formulas
- horizon-specific data windows
- portfolio similarity and duplicate removal
- missing-data severity and fallback behavior
- same-sector second-stock admission
- correlation thresholds and penalties
- initial portfolio weights
- scoring, rounding, validation, and output rules

No formula in this document may be silently changed. A change requires a versioned documentation update, validation evidence, and backward-compatibility review.

## 2. Global Calculation Rules

The Portfolio Confidence Index (PCI) contains five permanent components:

| Component | Code | Default weight |
|---|---:|---:|
| Average AI Confidence | AIC | 25% |
| Sector Balance | SB | 20% |
| Correlation Balance | CB | 20% |
| Risk Distribution | RD | 20% |
| Expected Return Balance | ERB | 15% |

The initial formula is:

`PCI = 0.25 × AIC + 0.20 × SB + 0.20 × CB + 0.20 × RD + 0.15 × ERB`

Every component must be normalized to `0–100` before weighting. All weights must be non-negative and must sum to exactly `1.00` within a numerical tolerance of `1e-9`.

> **Engineering Decision ED-001 — Central PCI Weight Configuration**
>
> PCI weights will be read from one centralized configuration structure. The default v1.0 values are AIC 25%, SB 20%, CB 20%, RD 20%, and ERB 15%. They will not change during v1.0. The values must never be repeated as independent literals in calculation or UI code. Future A/B testing and calibration may update only the centralized structure after a versioned decision and validation process.

## 3. Portfolio Confidence Index Component Formulas

### 3.1 Average AI Confidence — AIC

#### Inputs

For every holding:

- AI Confidence for the selected horizon
- portfolio weight
- calculation timestamp
- data end date
- confidence model/version identifier when available

#### Formula

`AIC = Σ(wᵢ × AIᵢ) / Σ(wᵢ)`

For v1.0 equal-weight portfolios this is the arithmetic mean. Valid AI Confidence inputs are numerical values in `0–100`.

#### Missing-data and minimum-data rules

- All holdings should have horizon-matched AI Confidence.
- A non-finite, non-numeric, or out-of-range value is invalid.
- One missing AI Confidence in an otherwise calculable portfolio is **MEDIUM**: replace only that component input with the mean AI Confidence of the other valid holdings, apply a fixed `8`-point penalty to AIC, and add a warning.
- More than one missing AI Confidence, or no valid confidence values, is **CRITICAL** and causes Reject.
- Imputation may never raise AIC above the pre-penalty valid-holding mean.

#### Boundaries

- `0–49.9`: weak
- `50–69.9`: moderate
- `70–84.9`: strong
- `85–100`: very strong

The final AIC is clamped to `0–100`.

> **Engineering Decision ED-004 — Conservative AI Confidence Imputation**
>
> A single missing confidence value does not make the entire portfolio mathematically impossible. A conservative mean substitution plus an explicit penalty preserves usability without presenting incomplete data as fully reliable. Multiple missing values are rejected because the confidence component would no longer represent the portfolio.

### 3.2 Sector Balance — SB

#### Inputs

- sector of every holding
- holding weights
- represented sector count
- total weight per sector
- sector concentration measured by HHI

`Sector HHI = Σ(sector_weightⱼ²)`

#### Sector-count score — SNS

| Represented sectors | SNS |
|---:|---:|
| 1 | 0 |
| 2 | 40 |
| 3 | 90 |
| 4 | 100 |
| 5 or more | 90 |

Optimizer constraints normally require 3–4 represented sectors.

#### Concentration score — HCS

For `S` represented sectors:

`Ideal HHI = 1 / S`

`HCS = 100 × [1 - ((Sector HHI - Ideal HHI) / (1 - Ideal HHI))]`

HCS is clamped to `0–100`.

#### Dominant-sector score — DSS

- maximum sector weight `≤ 30%`: `100`
- `30–40%`: linear interpolation from `100` to `60`
- `40–50%`: linear interpolation from `60` to `0`
- `> 50%`: `0`, followed by Reject because the hard concentration constraint is violated

#### Final formula

`SB = 0.35 × SNS + 0.40 × HCS + 0.25 × DSS`

#### Missing-data and minimum-data rules

- All holdings should have a known sector.
- One unknown sector with a weight `≤ 25%` is **MEDIUM**: assign it temporarily to `Unclassified`, apply a fixed `12`-point penalty to SB, and add a warning.
- More than one unknown sector, or unknown-sector weight `> 25%`, is **CRITICAL** and causes Reject.
- Two represented sectors is **MEDIUM** only for diagnostic evaluation: apply a further `15`-point SB penalty and exclude the result from the default Top 20 unless fewer than 20 valid portfolios exist.
- A sector exceeding `50%` is **CRITICAL** and causes Reject.

> **Engineering Decision ED-005 — HHI-Based Sector Balance**
>
> Sector count alone can create cosmetic diversification. HHI measures the actual distribution of sector weights, while SNS and DSS preserve understandable penalties for too few sectors and a dominant sector. `Unclassified` is allowed only as a penalized temporary state for one small exposure.

### 3.3 Correlation Balance — CB

Only return correlations may be used. Raw price correlations are forbidden.

#### Required inputs

- average pairwise correlation
- maximum pairwise correlation
- high-correlation pair count
- extreme-correlation pair count
- stress-period correlation
- total pair count

Negative correlations are retained in stored numerical facts. For the diversification score, values below zero are treated as zero and cannot create a score above 100.

#### Average-correlation score — ACS

Use linear interpolation between these points:

| Average correlation | ACS |
|---:|---:|
| `≤ 0.25` | 100 |
| `0.45` | 80 |
| `0.65` | 50 |
| `0.80` | 20 |
| `1.00` | 0 |

#### Maximum-pair score — MCS

Use linear interpolation between these points:

| Maximum pair correlation | MCS |
|---:|---:|
| `≤ 0.45` | 100 |
| `0.65` | 70 |
| `0.80` | 30 |
| `1.00` | 0 |

#### High-pair score — HPS

A high-correlation pair has `correlation ≥ 0.65`.

`HPS = 100 × (1 - high_pair_count / total_pair_count)`

For every extreme pair with `correlation ≥ 0.80`, subtract an additional `10` points. Clamp HPS to `0–100`.

#### Stress-correlation score — SCS

SCS uses the ACS interpolation table. If stress correlation is `> 0.80`, SCS may not exceed `20`.

#### Final formula

`CB = 0.40 × ACS + 0.25 × MCS + 0.15 × HPS + 0.20 × SCS`

#### Missing-data and minimum-data rules

- All return series must be aligned on common valid dates.
- A pair below the horizon minimum observation count is invalid.
- If one pair is unavailable but at least `90%` of all pairs and every holding remain represented, the condition is **MEDIUM**: use the worse of the available maximum correlation and `0.65` for that missing pair, subtract `10` points from CB, and add a warning.
- More than one missing pair, less than `90%` pair coverage, or a holding with no valid pair relationship is **CRITICAL** and causes Reject.
- Missing stress correlation with otherwise complete normal correlation is **MEDIUM**: set SCS to `40`, subtract a further `5` points from CB, and add a warning.
- A non-positive-variance return series is **CRITICAL** and causes Reject.

> **Engineering Decision ED-006 — Multi-Layer Return Correlation**
>
> Average correlation alone can hide one dangerous pair. CB therefore combines average, maximum pair, high-pair count, and stress correlation. Conservative substitution is permitted for one missing pair or missing stress sample, but the uncertainty must reduce the score and remain visible to the user.

### 3.4 Risk Distribution — RD

#### Inputs

For every holding:

- Sell Risk in `0–100`
- horizon-specific volatility
- downside deviation
- portfolio weight
- approximate contribution to total portfolio risk

Volatility and downside deviation are converted to percentile ranks within the valid same-horizon Smart Scanner candidate universe.

`Stock Riskᵢ = 0.45 × Sell Riskᵢ + 0.30 × Volatility Percentileᵢ + 0.25 × Downside Deviation Percentileᵢ`

`Risk Contributionᵢ = (wᵢ × Stock Riskᵢ) / Σ(w × Stock Risk)`

#### Risk-balance score — RBS

`Risk HHI = Σ(Risk Contributionᵢ²)`

`Ideal Risk HHI = 1 / N`

`RBS = 100 × [1 - ((Risk HHI - Ideal Risk HHI) / (1 - Ideal Risk HHI))]`

#### Average-risk quality — ARQ

`Weighted Risk = Σ(wᵢ × Stock Riskᵢ)`

`ARQ = 100 - Weighted Risk`

#### Dominant-risk score — DRS

- maximum risk contribution `≤ 30%`: `100`
- `30–40%`: linear interpolation from `100` to `60`
- `40–50%`: linear interpolation from `60` to `0`
- `> 50%`: `0`

#### Final formula

`RD = 0.50 × RBS + 0.30 × ARQ + 0.20 × DRS`

#### Missing-data and minimum-data rules

- The percentile reference universe should contain at least 20 valid same-horizon candidates.
- A reference universe of 10–19 candidates is **MEDIUM**: calculate percentiles, subtract `8` points from RD, and warn that the risk reference universe is narrow.
- Fewer than 10 reference candidates is **CRITICAL** and causes Reject.
- One missing Sell Risk, volatility, or downside-deviation value is **MEDIUM**: substitute the candidate-universe 75th percentile for the missing input, subtract `10` points from RD, and add a warning.
- More than one holding with incomplete risk inputs is **CRITICAL** and causes Reject.
- Maximum risk contribution above `50%` is **MEDIUM**: the portfolio remains calculable, DRS becomes zero, an additional `5`-point RD penalty applies, and a concentration warning is added.

> **Engineering Decision ED-007 — Risk Contribution Before Raw Volatility**
>
> Portfolio resilience depends on how risk is distributed, not only on average volatility. The v1.0 proxy combines sell risk, volatility, and downside behavior, then measures concentration with HHI. Conservative 75th-percentile substitution ensures missing risk data cannot improve a score.

### 3.5 Expected Return Balance — ERB

#### Inputs

- horizon-specific expected return for every holding
- portfolio weight
- expected-return distribution of the valid same-horizon candidate universe

Expected returns are winsorized at the candidate universe's 5th and 95th percentiles for scoring only. Original values remain available in numerical facts.

#### Return-quality score — RQS

Each winsorized expected return is converted to a `0–100` percentile rank within the valid candidate universe.

`RQS = Σ(wᵢ × Return Percentileᵢ)`

#### Return-balance score — EBS

`CV = standard_deviation(expected_returns) / max(abs(mean_expected_return), ε)`

`EBS = 100 × [1 - min(CV, 1.50) / 1.50]`

If portfolio mean expected return is zero or negative, EBS may not exceed `40`.

#### Return-contribution score — RCS

`Contributionᵢ = wᵢ × max(expected_returnᵢ, 0)`

If total positive contribution is zero, `RCS = 0`. Otherwise:

`Return HHI = Σ(normalized_contributionᵢ²)`

`Ideal Return HHI = 1 / N`

`RCS = 100 × [1 - ((Return HHI - Ideal Return HHI) / (1 - Ideal Return HHI))]`

#### Final formula

`ERB = 0.45 × RQS + 0.35 × EBS + 0.20 × RCS`

#### Missing-data and minimum-data rules

- The percentile reference universe should contain at least 20 valid same-horizon candidates.
- A universe of 10–19 candidates is **MEDIUM**: calculate the component, subtract `8` points from ERB, and add a warning.
- Fewer than 10 reference candidates is **CRITICAL** and causes Reject.
- One missing expected return is **MEDIUM**: substitute the lower of zero and the candidate-universe 25th percentile, subtract `10` points from ERB, and add a warning.
- More than one missing expected return is **CRITICAL** and causes Reject.
- All non-positive expected returns are **LOW**: retain the calculation and add a warning; EBS remains capped at 40.

> **Engineering Decision ED-008 — Balanced Expected Return, Not Maximum Return**
>
> ERB rewards reasonable return quality across several holdings and penalizes dependence on one outlier. Winsorization limits unstable forecasts, while conservative substitution prevents missing return data from creating an artificial advantage.

## 4. Time Horizons and Data Windows

| Portfolio horizon | Lookback | Return frequency | Minimum common observations | Correlation window | Stress window |
|---|---:|---|---:|---:|---:|
| Daily | 6 months | Daily | 80 trading days | Last 60 trading days | 20 trading days |
| Weekly | 1 year | Daily | 160 trading days | Last 120 trading days | 30 trading days |
| Monthly | 2 years | Weekly | 80 weeks | Last 52 weeks | 12 weeks |
| Quarterly | 3 years | Weekly | 120 weeks | Last 104 weeks | 26 weeks |
| 6-month | 5 years | Weekly | 180 weeks | Last 156 weeks | 39 weeks |
| Yearly | 7 years | Weekly | 250 weeks | Last 208 weeks | 52 weeks |

Returns are calculated as:

`returnₜ = adjusted_closeₜ / adjusted_closeₜ₋₁ - 1`

Rules:

- Adjusted closing prices are preferred.
- Missing dates are not forward-filled for return calculation.
- Weekly close is the final valid trading observation of the week.
- Every horizon has an independent return matrix, score set, cache key, and result.
- A longer horizon may use a shorter available history only when it still meets the stated minimum observation count; this is **LOW** and produces a shortened-lookback warning.
- Failing the minimum common observation count is handled under the correlation severity rules.

The stress period is the contiguous stress window within the lookback that produces the worst cumulative return for an equal-weight reference basket. Stress correlation is calculated from holding returns inside that window. Future data must never participate in window selection.

> **Engineering Decision ED-009 — Horizon-Specific Independent Evidence**
>
> Short horizons require responsive daily observations, while longer horizons require enough history to observe multiple market regimes and use weekly returns to reduce daily noise. No horizon may reuse another horizon's correlations or component scores.

## 5. Portfolio Similarity and Top 20 Duplicate Control

For holding sets `A` and `B`:

`Jaccard = |A ∩ B| / |A ∪ B|`

`Overlap = |A ∩ B| / min(|A|, |B|)`

For aligned holding weights:

`Weight Similarity = 1 - 0.5 × Σ|wAᵢ - wBᵢ|`

For aligned sector weights:

`Sector Similarity = 1 - 0.5 × Σ|sAⱼ - sBⱼ|`

Two portfolios are excessive near-duplicates if any of these rules is met:

1. Their holding sets are identical.
2. `Overlap ≥ 0.75` and `Jaccard ≥ 0.60`.
3. `Overlap ≥ 0.67`, `Weight Similarity ≥ 0.85`, and `Sector Similarity ≥ 0.90`.

When two portfolios are excessive near-duplicates, retain them in this order of preference:

1. higher raw PCI
2. higher CB
3. higher RD
4. lower maximum pair correlation
5. lexicographically smaller stable portfolio ID

Duplicate removal is a ranking operation, not a PCI penalty. A removed near-duplicate may be recorded in diagnostics but is not shown in the Top 20.

> **Engineering Decision ED-010 — Holdings First, Weights and Sectors Second**
>
> The Top 20 must represent materially different choices. Holding overlap is the primary test because changing only one weak stock should not create another headline portfolio. Weight and sector similarity catch structurally equivalent portfolios whose holding counts differ.

## 6. Missing-Data Severity Policy

Every missing or invalid datum must be classified before scoring.

### 6.1 Severity levels

#### CRITICAL → Reject

Use only when the calculation is impossible, violates a hard portfolio constraint, or would require material fabrication. The portfolio is not ranked and receives no final PCI.

#### MEDIUM → Warning + Score Penalty

The portfolio remains calculable through a documented conservative fallback. The affected PCI component receives the exact stated penalty and a structured warning is added.

#### LOW → Warning Only

The core calculation remains valid and no PCI component is changed. The user receives a structured informational warning.

### 6.2 Consolidated classification table

| Condition | Severity | Action |
|---|---|---|
| No valid AI Confidence or more than one missing | CRITICAL | Reject |
| One missing AI Confidence | MEDIUM | Valid-holding mean, AIC −8, warning |
| More than one missing sector or unknown weight >25% | CRITICAL | Reject |
| One missing sector with weight ≤25% | MEDIUM | `Unclassified`, SB −12, warning |
| Sector weight >50% | CRITICAL | Reject |
| Only two represented sectors | MEDIUM | SB −15, warning, restricted Top 20 admission |
| Non-positive-variance return series | CRITICAL | Reject |
| Pair coverage <90% or more than one missing pair | CRITICAL | Reject |
| One missing pair with ≥90% coverage | MEDIUM | Conservative 0.65/worse substitution, CB −10, warning |
| Missing stress correlation | MEDIUM | SCS=40, CB −5, warning |
| Reference universe <10 | CRITICAL | Reject |
| Reference universe 10–19 | MEDIUM | Affected component −8, warning |
| One incomplete holding risk input | MEDIUM | 75th-percentile risk substitution, RD −10, warning |
| Multiple incomplete holding risk inputs | CRITICAL | Reject |
| Maximum risk contribution >50% | MEDIUM | DRS=0, RD −5, warning |
| One missing expected return | MEDIUM | Conservative substitution, ERB −10, warning |
| Multiple missing expected returns | CRITICAL | Reject |
| All expected returns non-positive | LOW | Warning only; EBS cap remains part of normal formula |
| Shortened lookback that meets minimum observations | LOW | Warning only |
| Missing News Impact | LOW | Warning only; no PCI effect |
| Missing company narrative metadata | LOW | Warning only |

Penalties are applied after the affected component formula and before component clamping. Multiple MEDIUM penalties within one component are cumulative. A component cannot fall below zero.

Each warning must include:

- severity
- warning code
- affected holding or component
- fallback used
- numerical penalty, if any
- human-readable explanation

> **Engineering Decision ED-011 — Three-Level Graceful Degradation**
>
> Reject is reserved for cases where calculation integrity cannot be preserved. Documented conservative fallbacks keep partially incomplete but usable portfolios visible, while score penalties prevent them from outranking equally strong portfolios with complete evidence.

## 7. Same-Sector Second-Stock Rule

The normal rule allows a second holding from the same sector only when all of these conditions are satisfied:

1. Sector Score is at least `75`.
2. Pair correlation is at most `0.45`.
3. PCI improves by at least `+2.0` raw points against the best same-size alternative using another sector.
4. Combined sector weight does not exceed `40%`.
5. The portfolio retains at least three represented sectors.
6. Maximum pair correlation does not exceed `0.65`.
7. The second holding's AI Confidence is at least `70`.
8. RD does not fall by more than `5.0` points.

The comparison must use portfolios with the same holding count and the same weighting method.

> **Engineering Decision ED-002 — High Sector Override**
>
> The default maximum same-sector pair correlation remains `0.45`. AI may accept correlation up to and including `0.55` only when all four override conditions are simultaneously true: Sector Score `≥ 90`, the second holding's AI Confidence `≥ 85`, raw PCI improvement `≥ +3.0`, and Risk Distribution does not decrease. All other normal constraints, including the 40% sector-weight limit and minimum three sectors, remain active. When applied, warnings must contain the exact text `High Sector Override Applied`.

The override is deterministic. Narrative AI may explain the result but may not independently waive a threshold.

## 8. Correlation Thresholds and Penalties

| Correlation | Classification |
|---:|---|
| `≤ 0.25` | Low / excellent diversification |
| `> 0.25–0.45` | Good |
| `> 0.45–0.65` | Moderate |
| `> 0.65–0.80` | High |
| `> 0.80` | Extreme |

Rules:

- Every pair `≥ 0.65` participates in the HPS proportional penalty.
- Every pair `≥ 0.80` subtracts an additional 10 HPS points.
- Stress correlation `≤ 0.45` receives no extra warning.
- Stress correlation `> 0.65` creates a high-stress-correlation warning.
- Stress correlation `> 0.80` caps SCS at 20.
- If stress correlation exceeds normal average correlation by at least `0.20`, add `Diversification Weakens Under Stress` to warnings.
- Correlation exactly on a threshold belongs to the lower-risk band except `0.65` and `0.80`, which activate their stated penalties.

> **Engineering Decision ED-012 — Explicit Correlation Bands and Stress Penalties**
>
> Fixed bands make ranking reproducible and explanations understandable. Stress penalties are separate because normal-market diversification can disappear during drawdowns. Negative correlation receives no bonus beyond the maximum diversification score, preventing leverage toward unstable negative relationships.

## 9. Portfolio Weights

The v1.0 optimizer uses equal weights:

`wᵢ = 1 / N`

Examples:

- 4 holdings: 25% each
- 5 holdings: 20% each
- 6 holdings: approximately 16.6667% each internally

Score-weighted, risk-weighted, and optimized weights are outside v1.0.

> **Engineering Decision ED-013 — Equal Weights in v1.0**
>
> Equal weighting isolates PCI engine quality from weight-optimization effects, reduces overfitting, improves explainability, and makes validation reproducible. Future weighting methods must preserve equal weight as a comparable baseline.

## 10. News Impact

News Impact is not one of the five permanent PCI components. Missing or extreme News Impact must not directly modify AIC, SB, CB, RD, ERB, or final PCI in v1.0.

> **Engineering Decision ED-003 — News Impact Outside PCI in v1.0**
>
> News Impact will be used only for AI explanations and the warning system in v1.0. It will not directly change PCI. Direct integration may be evaluated in v2.x only after source reliability, timestamp alignment, sentiment calibration, and backtesting are validated.

## 11. Scoring, Precision, Clamping, and Rounding

### 11.1 Internal precision

- Use at least IEEE 754 64-bit floating-point precision.
- Do not round intermediate component calculations.
- Preserve correlations to at least six decimal places internally.
- Normalize portfolio weights to `1.0` before calculation.

### 11.2 Clamping

Apply:

`clamp(x) = min(100, max(0, x))`

Clamping occurs:

1. after each subscore formula
2. after documented penalties for the component
3. after final weighted PCI calculation

### 11.3 NaN and infinity

NaN, positive infinity, negative infinity, and non-numeric values are invalid. They must follow the missing-data severity policy. They must never silently become zero or reach the UI.

### 11.4 Output precision

| Output | Precision |
|---|---:|
| Internal calculation | Full available precision |
| Structured/API PCI and components | 4 decimals |
| Main UI PCI | 1 decimal |
| UI component scores | 1 decimal |
| UI correlations | 2 decimals |
| UI weights | 1 decimal percentage |
| Downloadable numerical report | 4 decimals |

Ranking always uses unrounded raw PCI.

Tie-break order:

1. higher raw CB
2. higher raw RD
3. higher raw SB
4. higher raw AIC
5. lower maximum pair correlation
6. stable portfolio ID

> **Engineering Decision ED-014 — Late Rounding and Deterministic Ranking**
>
> Early rounding can reverse close portfolio rankings and create inconsistent results between UI and engine. Calculations therefore keep full precision, ranking uses raw values, and rounding occurs only at output boundaries.

## 12. Output Contract and Explainability

Every portfolio result must contain at least:

- `portfolio_id`
- `status`
- `horizon`
- `calculation_timestamp`
- `data_end_date`
- `stocks`
- `sectors`
- `weights`
- `portfolio_confidence_index`
- `average_ai_confidence`
- `sector_balance_score`
- `correlation_balance_score`
- `risk_distribution_score`
- `expected_return_balance_score`
- `average_correlation`
- `maximum_pair_correlation`
- `high_correlation_pair_count`
- `extreme_correlation_pair_count`
- `stress_correlation`
- `sector_weights`
- `maximum_sector_weight`
- `maximum_risk_contribution`
- `expected_return_summary`
- `explanation_facts`
- `warnings`
- `rejection_reasons`

Allowed status values:

- `valid`
- `valid_with_warnings`
- `rejected`

Narrative explanations must:

- derive only from stored numerical facts and warnings
- identify strongest and weakest components by actual score comparison
- disclose MEDIUM fallbacks that materially affect ranking
- avoid guarantees and definitive buy/sell commands
- preserve the user's final decision authority

> **Engineering Decision ED-015 — Facts Before Narrative**
>
> Numerical facts are the source of truth. Narrative AI may summarize, compare, and explain those facts, but it may not invent a cause, conceal a penalty, change a status, or override a deterministic threshold.

## 13. Binding Technical Decision Inventory

The following 24 technical decisions are binding for v1.0:

1. PCI contains exactly five permanent components.
2. Default component weights are 25/20/20/20/15.
3. PCI weights come from one centralized configuration structure.
4. Every component and final PCI are normalized to `0–100`.
5. AIC is the portfolio-weighted mean of horizon-matched AI Confidence.
6. Sector balance combines sector count, sector HHI, and maximum sector weight.
7. Correlation uses returns, never raw prices.
8. CB combines average, maximum-pair, high-pair-count, and stress correlation evidence.
9. RD combines risk quality with risk-contribution concentration.
10. ERB rewards distributed expected-return quality rather than maximum forecast return.
11. Every horizon uses an independent lookback, return matrix, cache key, and score result.
12. Stress correlation uses the worst contiguous reference-basket window inside the lookback.
13. Excessive near-duplicates are removed from Top 20 after raw PCI ranking.
14. Missing data follows CRITICAL, MEDIUM, or LOW severity.
15. CRITICAL causes Reject; MEDIUM causes warning and component penalty; LOW causes warning only.
16. Conservative fallback values may never improve the affected component.
17. Default same-sector second-stock maximum correlation is 0.45.
18. The ED-002 override may extend that limit to 0.55 only when all four override conditions pass.
19. A same-sector pair remains subject to a 40% combined sector-weight limit.
20. The v1.0 optimizer uses equal portfolio weights.
21. News Impact does not directly modify PCI in v1.0.
22. Intermediate calculations are not rounded; ranking uses raw PCI.
23. NaN and infinite values never reach the UI and follow severity policy.
24. Narrative explanations derive only from numerical facts and structured warnings.

## 14. Implementation and Validation Order

Implementation must follow this order:

1. data contracts and centralized constants
2. sector engine
3. PCI engine
4. optimizer and duplicate control
5. optimizer UI
6. numerical and narrative portfolio report

Every stage must preserve previous stages and validate:

- Dashboard startup and primary flow
- Smart Scanner startup, scan, filtering, and stored results
- login and existing session keys
- YEB PRO protected modules and persisted user data
- dark/light theme behavior
- no raw traceback or raw HTML exposure
- no repeated expensive market request during page navigation

## 15. Future Improvements

The following items are roadmap candidates and are explicitly outside v1.0 implementation scope:

- Risk parity weighting
- Minimum variance portfolio
- Dynamic PCI weights
- PCI A/B testing and calibration
- Machine learning weighting
- Bayesian portfolio optimizer
- Adaptive sector allocation
- Direct News Impact integration
- Capital Flow Engine
- Portfolio stress simulation
- Portfolio rebalancing AI
- Transaction-cost and liquidity optimization
- Lot-size-aware allocation
- Regime-aware correlation models
- Robust covariance estimation
- Black–Litterman-style views
- Tax-aware portfolio optimization
- User-specific risk preference calibration
- Walk-forward portfolio validation
- Automated drift monitoring

Roadmap items do not authorize code changes. Each requires its own specification, validation criteria, and versioned engineering decision before implementation.

## 16. Final Acceptance Rule

An implementation conforms to this appendix only when:

- all 24 binding technical decisions are implemented or explicitly marked not yet in scope
- all 15 Engineering Decisions remain traceable to implementation and tests
- penalties and warnings are deterministic and reproducible
- a rejected portfolio never receives a ranked final PCI
- a valid-with-warnings portfolio exposes every applied fallback and penalty
- existing protected workflows remain operational
- local tests and application smoke checks pass

