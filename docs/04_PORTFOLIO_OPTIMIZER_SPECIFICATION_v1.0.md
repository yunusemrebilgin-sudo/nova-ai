# Portfolio Optimizer Specification v1.0

## 1. Purpose
Generate and rank the strongest 20 portfolios for a selected time horizon.

## 2. Candidate Source
Use Smart Scanner results as the candidate universe.

Default:
- top 50 valid scanner candidates

Do not rescan the entire market inside the optimizer.

## 3. Portfolio Constraints
- 4–6 stocks
- 3–4 sectors
- normally 1 stock per sector
- maximum 2 from one sector
- no sector above 50% weight
- reject portfolios with insufficient data

## 4. Optimization Objective
Primary objective:
- maximize Portfolio Confidence Index

Secondary objectives:
- improve diversification
- limit concentration
- preserve expected return quality
- avoid duplicate-like portfolios in Top 20

## 5. Combination Strategy
Do not brute-force all combinations if computationally expensive.

Preferred pipeline:
1. filter invalid candidates
2. group by sector
3. select sector leaders
4. build constrained candidate combinations
5. compute PCI
6. remove near-duplicate portfolios
7. rank top 20

## 6. Time-Horizon Separation
Run independently for:
- daily
- weekly
- monthly
- quarterly
- 6-month
- yearly

Do not reuse one horizon's correlations or scores for another horizon.

## 7. Duplicate Control
Two portfolios are near-duplicates if most holdings are the same.

The Top 20 list must not contain many copies differing by only one weak stock.

## 8. Weights
Initial release may use equal weights.

Later versions may support optimized weights, but must preserve:
- sector concentration limits
- risk contribution limits
- explainability

## 9. Ranking Output
For each portfolio:
- rank
- portfolio name/id
- component scores
- holdings
- sectors
- weights
- expected return summary
- risk summary
- numeric explanation
- narrative explanation

## 10. Performance
- cache repeated data
- reuse scanner data
- reuse return matrices
- avoid repeated yfinance calls
- store results in session state for page navigation

## 11. Safety
Optimizer must not modify:
- Smart Scanner rankings
- existing Dashboard calculations
- existing YEB PRO position data
- authentication/session behavior
