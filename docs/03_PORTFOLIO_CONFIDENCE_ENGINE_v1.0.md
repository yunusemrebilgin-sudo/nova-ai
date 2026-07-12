# Portfolio Confidence Engine Specification v1.0

## 1. Purpose
The Portfolio Confidence Index (PCI) scores the quality and resilience of a portfolio for a selected time horizon.

## 2. Permanent Components
The PCI must always contain these five components:

1. Average AI Confidence
2. Sector Balance
3. Correlation Balance
4. Risk Distribution
5. Expected Return Balance

Initial weights:
- Average AI Confidence: 25%
- Sector Balance: 20%
- Correlation Balance: 20%
- Risk Distribution: 20%
- Expected Return Balance: 15%

Weights must be constants in one location and must sum to 100%.

## 3. Final Formula
`PCI = 0.25*AIC + 0.20*SB + 0.20*CB + 0.20*RD + 0.15*ERB`

Each component is normalized to 0–100 before weighting.

## 4. Average AI Confidence
Input:
- individual stock AI confidence scores
- optional position weights

Rules:
- weighted average if weights exist
- otherwise equal-weight average
- missing scores must not silently become zero
- invalid candidates are excluded

## 5. Sector Balance
Portfolio defaults:
- 4–6 stocks
- 3–4 sectors
- normally 1 stock per sector
- maximum 2 from the same sector only when PCI improves

Sector Balance should reward:
- 3–4 represented sectors
- no dominant sector
- balanced weights

Sector Balance should penalize:
- one sector exceeding 50%
- fewer than 3 sectors
- repeated same-sector exposure without measurable PCI improvement

## 6. Correlation Balance
Use return correlations, never raw price correlations.

Required measures:
- average pairwise correlation
- maximum pairwise correlation
- count of highly correlated pairs
- stress-period correlation

Initial interpretation:
- 0.00–0.25: excellent diversification
- 0.25–0.45: good
- 0.45–0.65: moderate
- 0.65–0.80: weak
- above 0.80: concentrated risk

Correlation Balance must not rely only on the average. Maximum-pair and stress correlation must also apply penalties.

Same-sector second-stock rule:
A second stock from the same sector is allowed only if:
1. sector strength is high,
2. pair correlation is below threshold,
3. total PCI increases.

## 7. Risk Distribution
Inputs may include:
- sell risk
- volatility
- ATR or existing volatility metric
- concentration
- downside behavior

Reward:
- balanced risk contributions
- no single stock dominating portfolio risk
- low concentration

Penalize:
- one stock contributing excessive portfolio risk
- high combined sell risk
- high volatility concentration

## 8. Expected Return Balance
This component does not simply maximize return.

Reward:
- reasonable expected returns across multiple holdings
- absence of one unrealistic outlier
- consistency with the selected horizon

Penalize:
- one stock carrying nearly all expected return
- extremely dispersed return expectations
- high expected return combined with extreme risk concentration

## 9. Score Validations
- Every component must remain between 0 and 100.
- Final PCI must remain between 0 and 100.
- No NaN/inf values may reach the UI.
- Portfolios with missing critical data must be rejected or marked incomplete.
- The engine must return both final score and component breakdown.

## 10. Output Contract
Each portfolio result must include:
- portfolio_id
- horizon
- stocks
- sectors
- weights
- portfolio_confidence_index
- average_ai_confidence
- sector_balance_score
- correlation_balance_score
- risk_distribution_score
- expected_return_balance_score
- average_correlation
- maximum_pair_correlation
- high_correlation_pair_count
- stress_correlation
- explanation_facts
- warnings

## 11. Explainability
The narrative layer must derive from numeric facts.

Example:
“Portföy güven endeksi, yüksek AI güveni ve dengeli sektör dağılımı sayesinde yükseldi. En yüksek korelasyonlu çift X–Y olduğu için korelasyon bileşeni diğer bileşenlerden daha düşük kaldı.”

No invented reasons.
