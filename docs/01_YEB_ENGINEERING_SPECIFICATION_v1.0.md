# YEB Engineering Specification v1.0

## 1. Purpose
This document is the binding engineering reference for YEB. It defines the current architecture, extension rules, module responsibilities, compatibility rules, and implementation order.

## 2. Product Definition
YEB is an AI-assisted investment decision-support platform. It does not promise returns and does not issue definitive buy/sell instructions. It explains the evidence behind its analyses.

## 3. Core Product Structure
1. Dashboard — public, summary-oriented.
2. Smart Scanner — authenticated access.
3. YEB PRO — paid/premium workspace for tracking, simulation, journaling, and notifications.
4. Portfolio Optimizer — portfolio-level intelligence built on Smart Scanner output.
5. Portfolio Report — explainable numerical and narrative portfolio analysis.

## 4. Existing Codebase
Current modules:
- `app.py`: orchestration, navigation, page rendering, authentication flow, Streamlit state coordination.
- `analytics.py`: technical and analytical calculations.
- `scanner.py`: market scanning and candidate generation.
- `decision_center.py`: trade-horizon and decision-support logic.
- `portfolio.py`: existing portfolio-related logic; primary home for new portfolio confidence and optimizer engines.
- `signals.py`: signal-related calculations.
- `news.py`: news and news-impact logic.
- `theme.py`: visual themes and UI tokens.
- `user_store.py`: users, access, and account-related logic.
- `utils.py`: shared utilities.
- `data/`: local reference datasets.

## 5. Existing YEB PRO Modules — Protected
The following are already implemented and must not be rewritten:
- Aldım
- Sattım
- Pozisyon Takibi
- Simülasyon
- Trade Journal
- Bildirimler

Known render functions include:
- `render_pro_buy_page`
- `render_pro_sell_page`
- `render_pro_positions_page`
- `render_pro_simulation_page`
- `render_trade_journal_page`
- `render_pro_notifications_page`
- `render_yeb_pro_page`

## 6. Core Protection Rule
Working modules are extended, not replaced.

Forbidden unless explicitly requested:
- Rewriting `app.py`
- Replacing authentication or cookie handling
- Changing existing user/session keys
- Renaming existing pages or modules
- Altering current Dashboard, Smart Scanner, or YEB PRO behavior
- Removing existing calculations
- Breaking dark/light theme support
- Changing existing data persistence behavior

## 7. New Portfolio Architecture
Data flow:

Smart Scanner candidates  
→ Sector Engine  
→ Portfolio Confidence Engine  
→ Portfolio Optimizer  
→ Top 20 Portfolios  
→ Portfolio Report  
→ Optional YEB PRO tracking

## 8. Responsibility Boundaries
- `scanner.py`: produces ranked stock candidates only.
- `portfolio.py`: computes portfolio metrics, confidence scores, portfolio combinations, and portfolio reports.
- `analytics.py`: shared numerical calculations only.
- `news.py`: news impact only.
- `app.py`: UI integration only; no heavy optimization logic.
- `theme.py`: styling only.
- `user_store.py`: users and access only.

## 9. Time Horizons
Portfolio calculations must support:
- Daily
- Weekly
- Monthly
- Quarterly
- 6-month
- Yearly

Each horizon must use its own lookback and its own portfolio confidence result.

## 10. UI Principle
- Dashboard = summary, fast, minimal.
- YEB PRO = detailed management.
- Portfolio Optimizer page = ranked portfolio list and expandable detail.
- Portfolio Report = numeric explanation first, narrative explanation second.
- Never overload the first view.

## 11. Development Order
For every new capability:
1. Data model
2. Engine
3. Validation/tests
4. UI
5. Release

UI must not be built before engine outputs are stable.

## 12. Backward Compatibility
Every development part must verify:
- Dashboard still works
- Smart Scanner still works
- Login still works
- YEB PRO modules still work
- Theme switch still works
- Existing session state keys still work
- Existing live deployment still starts without error

## 13. Error Handling
- No traceback or raw HTML may be visible to users.
- Failed symbols must be skipped safely.
- Expensive operations must be cached.
- Missing data must degrade gracefully.

## 14. Explainability
Every portfolio score must be decomposable into its five permanent components:
1. Average AI Confidence
2. Sector Balance
3. Correlation Balance
4. Risk Distribution
5. Expected Return Balance

## 15. Acceptance Rule
A task is complete only when:
- The requested behavior works locally
- Existing protected modules remain functional
- No new runtime error appears
- The task's explicit checklist is verified
