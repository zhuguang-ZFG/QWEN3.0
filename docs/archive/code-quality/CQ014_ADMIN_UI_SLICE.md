# CQ-014 Slice 2: Admin UI Extraction

Date: 2026-05-25

## Problem

`routes/admin.py` mixed REST API handlers with ~280 lines of inline HTML/JS
templates, exceeding the 300-line project target and making admin API changes
harder to review.

## Decision

Move `ADMIN_HTML`, `ADMIN_BODY`, and `ADMIN_JS` into `routes/admin_ui.py` with
a single `render_admin_dashboard()` entry point. Keep auth, CSRF, and API routes
in `routes/admin.py`.

## Scope (this slice)

- New module: `routes/admin_ui.py` (~292 lines)
- `routes/admin.py` reduced to API + login/logout (~330 lines)
- Test: `tests/test_admin_ui.py`

## Out of scope

- Splitting admin API routes further (backends, stats, etc.)
- Externalizing CSS/JS to static files

## Verification

- `pytest tests/test_admin_ui.py tests/test_admin_csrf.py tests/test_access_guard.py -q`
- Full suite green before VPS deploy
- Public smoke after deploy
