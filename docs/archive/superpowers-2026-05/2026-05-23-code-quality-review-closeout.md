# 2026-05-23 Code Quality Review Closeout

> Scope: local review only. No production deployment in this pass.
> Trigger: user asked to learn the project and inspect code quality, then close out the findings according to Superpowers principles.

## Superpowers Mapping

| Principle | Closeout Action |
|---|---|
| Documentation first | This document records the code-quality findings before any fix implementation. |
| Small focused files | Findings are grouped into narrow follow-up slices instead of one broad refactor. |
| Local verification before deployment | Local compile passed; full pytest currently fails during collection and is recorded as evidence. |
| Never break production | No production files were changed or deployed in this review pass. |
| Best-practice reference | Recommendations favor explicit auth boundaries, atomic task claiming, and single-source routing config. |
| Progressive replacement | Large-file decomposition is deferred into independent slices with tests before integration. |

## Review Findings

| ID | Severity | Area | Evidence | Recommended Next Slice |
|---|---|---|---|---|
| CQ-001 | P0 | Test baseline | `python -m pytest -q --ignore=active_model` fails during collection because `tests/test_agent_task_routes.py` imports `_events` and `_tasks`, but `routes.agent_tasks` now uses `_TaskStore`. | Update the tests to use the current store contract or expose a test reset helper; then run the focused route suite and core suite. |
| CQ-002 | P0 | Agent task concurrency | `/agent/tasks/{task_id}/claim` allows `accepted`, `claimed`, and `running` tasks to be claimed again, overwriting `worker_id` and `lease_expires_at`. | Make claim atomic through SQLite conditional update: allow only `accepted` or expired leases, reject active running tasks with 409. |
| CQ-003 | P0 | Admin security | `routes/admin.py` still supports `?token=` and injects `_ADMIN_TOKEN` into page JavaScript. | Replace token-in-JS with HttpOnly Secure session cookie flow; remove query-token login and avoid exposing the long-lived admin token to browser JS. |
| CQ-004 | P1 | Private API boundary | `/v1/models` remains unauthenticated while private chat/message endpoints require `LIMA_API_KEY`. | Decide explicit policy: keep public only if needed for IDE discovery, otherwise require the same private key. |
| CQ-005 | P1 | Config drift | `backends.py` defines `THINKING_BACKENDS` twice; the later definition drops `longcat_web_think`. | Collapse backend capability lists to one source and add a regression test for thinking backend registration. |
| CQ-006 | P1 | Routing maintainability | `routing_engine.py` has retrieval injection logic inline and a separate `inject_retrieval_context()` helper with overlapping behavior. | Choose one path, delete duplication, and keep retrieval trace assertions in tests. |
| CQ-007 | P2 | File-size pressure | `smart_router.py`, `server.py`, `routing_engine.py`, and `http_caller.py` exceed the 300-line project target. | Continue gradual route/transport/config extraction after P0 fixes are green. |
| CQ-008 | P2 | Repository hygiene | `git status --short` shows many untracked reference repos, scripts, local data, and generated files. | Tighten `.gitignore` and document a commit checklist so production changes are not mixed with local experiments. |

## Verification Evidence

Commands run locally on 2026-05-23:

```text
python -m py_compile server.py routing_engine.py router_v3.py http_caller.py code_orchestrator.py routes\agent_tasks.py routes\admin.py routes\telegram.py tool_gateway\executor.py
```

Result: passed.

```text
python -m pytest -q --ignore=active_model
```

Result: failed during collection with:

```text
ImportError: cannot import name '_events' from 'routes.agent_tasks'
```

## Recommended Order

1. Fix `tests/test_agent_task_routes.py` against the current SQLite-backed task store and restore a passing focused route suite.
2. Harden atomic task claim and lease semantics with failing tests first.
3. Remove admin-token exposure from the HTML admin shell.
4. Decide and document `/v1/models` auth policy.
5. Consolidate backend capability config and retrieval injection duplication.
6. Continue `server.py` and router decomposition only after the P0 safety/test baseline is green.

## Deployment Status

No deployment was performed. These are review findings and follow-up slices, not live production changes.

## Implementation Pass 1

> Started after user approval on 2026-05-23.

Scope:

1. Restore the route-test baseline for the SQLite-backed task store.
2. Make active task leases non-overwritable.
3. Remove admin-token exposure from query-string login and browser JavaScript.

TDD plan:

1. Update `tests/test_agent_task_routes.py` to target the current `_TaskStore` contract and add claim lease regression coverage.
2. Add admin UI regression coverage proving `?token=` does not authenticate and the rendered page does not contain the configured admin token.
3. Run focused tests and confirm they fail for the intended missing behavior.
4. Implement the smallest route changes to pass.
5. Run focused tests plus compile verification.

Implementation result:

- `tests/test_agent_task_routes.py` now targets the current SQLite-backed `_TaskStore` through `_reset_for_tests()`.
- `/agent/tasks/{task_id}/claim` now rejects an active `running` or `claimed` lease with HTTP 409 and allows reclaim only after the stored lease expires.
- Admin UI login now sets a signed HttpOnly Secure session cookie derived from `LIMA_ADMIN_TOKEN`; the raw admin token is no longer stored in the browser cookie, accepted through `?token=`, or injected into page JavaScript.

Verification:

```text
python -m pytest tests\test_agent_task_routes.py tests\test_agent_task_contract.py tests\test_access_guard.py -q --ignore=active_model
```

Result: `40 passed`.

```text
python -m py_compile routes\agent_tasks.py routes\admin.py tests\test_agent_task_routes.py tests\test_access_guard.py
```

Result: passed.

```text
python -m pytest -q --ignore=active_model
```

Result: collection now succeeds, then the suite reports `345 passed, 8 failed, 8 skipped`.

Remaining full-suite failures after this slice:

- `tests/test_request_stats.py::test_record_request_looks_up_country_before_stats_lock`
- `tests/test_stream_footer.py::test_anthropic_speculative_stream_hides_backend_footer`
- `tests/test_stream_footer.py::test_anthropic_fake_stream_hides_backend_footer`
- Five `tests/test_telegram_bot.py::TestTelegramBot` failures related to test/env configuration and mocked API calls.

## Implementation Pass 2

> Trigger: user asked to continue checking all code.

Scope:

1. Review tracked Python project code, excluding local reference repositories and untracked experiments.
2. Resolve the remaining full-suite failures found after Pass 1.
3. Fix one concrete mojibake maintainability bug found during the broad scan.

Changes:

- Updated request-stat and Anthropic stream tests to patch the extracted modules (`routes.request_tracking` and `routes.anthropic_stream`) instead of stale `server.py` internals.
- Changed `telegram_bot.py` to read `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `GFW_PROXY` at call time instead of freezing them at import time.
- Replaced mojibake Telegram button/file-prefix text with ASCII labels in `telegram_bot.py`.
- Rewrote `routes/images.py` with a readable Chinese-character detector using `[\u4e00-\u9fff]` and added a regression test for Chinese prompt quality prefixing.

Verification:

```text
python -m pytest tests\test_image_endpoint_guard.py tests\test_request_stats.py tests\test_stream_footer.py tests\test_telegram_bot.py -q --ignore=active_model
```

Result: `20 passed`.

```text
python -m pytest -q --ignore=active_model
```

Result: `354 passed, 8 skipped`.

```text
tracked Python py_compile
```

Result: `215 files` passed.

Remaining warnings:

- `routes/telegram.py` still uses FastAPI `@router.on_event("startup")`, which is deprecated in favor of lifespan handlers.
- `tests/test_telegram_bot.py` still produces coroutine-not-awaited warnings when `_fire_and_forget` is mocked after coroutine creation. This is a test hygiene issue, not a failing runtime path.
