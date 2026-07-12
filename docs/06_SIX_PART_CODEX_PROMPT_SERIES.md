# Six-Part Codex Prompt Series

Run each part separately. Test and commit after every part.

---

## PART 1 — Data Model and Contracts

Read all docs in `/docs` first.

Goal:
Add portfolio data contracts without changing any UI.

Tasks:
1. Inspect current `portfolio.py`.
2. Add typed structures or clearly documented dict contracts for:
   - sector metrics
   - portfolio candidate
   - portfolio confidence result
   - portfolio report result
3. Add centralized constants for the five PCI weights.
4. Add validation helpers ensuring every component is 0–100.
5. Do not modify Dashboard, Smart Scanner, login, or YEB PRO UI.
6. Add tests/validation examples.
7. Report files changed.

Acceptance:
- Existing app behavior unchanged
- Portfolio data contracts available
- Five permanent components preserved

---

## PART 2 — Sector Engine

Read all docs in `/docs` first.
Preserve Part 1.

Goal:
Build sector analytics only. No portfolio generation and no UI.

Tasks:
1. Use existing stock/sector data.
2. Compute per-sector:
   - sector strength
   - sector momentum
   - sector trend
   - sector news impact
   - average Nova score
   - average AI confidence
   - final sector score
3. Support daily, weekly, monthly, quarterly, 6-month, yearly horizons.
4. Gracefully handle missing sector data.
5. Keep logic in `portfolio.py` or a clearly justified additive module.
6. Add validations.
7. Do not touch existing UI.

Acceptance:
- Sector engine returns structured horizon-specific results
- Existing app remains unchanged

---

## PART 3 — Portfolio Confidence Engine

Read all docs in `/docs` first.
Preserve Parts 1 and 2.

Goal:
Implement the five-component Portfolio Confidence Index.

Tasks:
1. Implement:
   - Average AI Confidence
   - Sector Balance
   - Correlation Balance
   - Risk Distribution
   - Expected Return Balance
2. Use the fixed initial weights from the specification.
3. For correlation use:
   - average pair correlation
   - maximum pair correlation
   - high-correlation pair count
   - stress correlation
4. Return final PCI plus full breakdown.
5. Validate all scores.
6. Add test cases for:
   - balanced portfolio
   - concentrated sector portfolio
   - highly correlated portfolio
   - missing-data portfolio
7. No UI changes.

Acceptance:
- PCI always 0–100
- All five components included
- Numeric facts available for explanations

---

## PART 4 — Portfolio Optimizer

Read all docs in `/docs` first.
Preserve Parts 1–3.

Goal:
Generate Top 20 portfolios from existing Smart Scanner candidates.

Tasks:
1. Reuse Smart Scanner output; do not rescan market.
2. Candidate universe default: first 50 valid stocks.
3. Generate portfolios with:
   - 4–6 stocks
   - 3–4 sectors
   - normally 1 stock per sector
   - max 2 from same sector only if PCI improves
4. Rank by PCI.
5. Remove near-duplicate portfolios.
6. Support all required horizons.
7. Cache reusable matrices/data.
8. Store optimizer result safely for page switching.
9. No UI changes.

Acceptance:
- Top 20 structured portfolio results generated
- Existing scanner behavior unchanged
- Performance acceptable

---

## PART 5 — Portfolio Optimizer Page

Read all docs in `/docs` first.
Preserve Parts 1–4.

Goal:
Add a new Portfolio Optimizer page without changing current pages.

Tasks:
1. Add a new page/menu entry additively.
2. Show horizon selector.
3. Show Top 20 portfolios ranked by PCI.
4. First view per portfolio:
   - rank
   - PCI
   - holdings
   - sectors
   - five component scores
5. Expanded detail:
   - correlation metrics
   - risk metrics
   - sector rationale
   - warnings
6. Keep Dashboard summary/minimal.
7. Do not modify existing YEB PRO modules.
8. Mobile-friendly and dark/light compatible.

Acceptance:
- New page works
- Existing pages unchanged
- No raw HTML/traceback

---

## PART 6 — AI Portfolio Intelligence and Report

Read all docs in `/docs` first.
Preserve Parts 1–5.

Goal:
Add numerical and narrative portfolio explanation/reporting.

Tasks:
1. Generate narrative explanations only from numeric facts.
2. Explain:
   - why this portfolio ranked highly
   - why sectors were selected
   - why a second stock from a sector was accepted/rejected
   - why PCI is not higher
   - weakest component
   - strongest component
3. Add optional detailed numeric report.
4. Add downloadable portfolio report content.
5. Avoid buy/sell commands and guarantees.
6. Do not expose private chain-of-thought; provide concise evidence-based rationale.
7. Do not alter existing YEB PRO trade tracking.
8. Add acceptance tests for explanation consistency.

Acceptance:
- Numeric and narrative report available
- Explanations match actual scores
- Existing system remains stable
