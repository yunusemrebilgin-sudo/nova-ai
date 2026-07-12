# Codex Development Guide v1.0

## Mandatory Reading
Before every task, read:
- `docs/01_YEB_ENGINEERING_SPECIFICATION_v1.0.md`
- `docs/02_YEB_PRODUCT_PRINCIPLES_v1.0.md`
- `docs/03_PORTFOLIO_CONFIDENCE_ENGINE_v1.0.md`
- `docs/04_PORTFOLIO_OPTIMIZER_SPECIFICATION_v1.0.md`

## Working Mode
Backward Compatibility Mode is mandatory.

## Forbidden
- Rewriting app.py
- Renaming current modules
- Changing current session state keys
- Replacing authentication/cookie logic
- Rebuilding YEB PRO modules
- Changing current scanner or decision logic unless explicitly required
- Mixing engine logic into UI code
- Claiming completion without tests

## Required Workflow
1. Inspect current implementation.
2. List files to modify.
3. Modify only those files.
4. Add tests or validation.
5. Run local checks.
6. Report exact changes.
7. Report any item not completed.

## File Responsibility
- portfolio logic → `portfolio.py`
- scanning → `scanner.py`
- shared analytics → `analytics.py`
- UI integration → `app.py`
- styles → `theme.py`
- users → `user_store.py`

## Completion Checklist
- App starts
- Dashboard opens
- Smart Scanner opens
- Login works
- YEB PRO modules open
- Existing simulation/trade data flow remains intact
- No raw traceback
- No raw HTML
- No new unnecessary dependency
- No repeated expensive network request on page navigation
