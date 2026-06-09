# LiMa Global Code Quality Follow-up P1 Plan

Date: 2026-05-23

## Goal

Close the remaining deployment-blocking quality gaps after the global code-quality hardening pass.

## Findings To Close

- Full pytest is red because prompt tests still assert the old chat role wording.
- `mimo_web*` backends are still in default `ide`/`chat` pools while their metadata says `sandbox_only`.
- `routing_engine.route()` has a core-path FC/tool call branch that depends on local untracked modules and reuses Telegram command heuristics.
- `session_memory/prompt_recall.py` is a runtime dependency but is not tracked.
- Identity leak filtering rewrites normal third-party factual statements too broadly.

## Tasks

- [x] Update prompt tests to match the new LiMa chat identity wording, then verify the focused prompt suite.
- [x] Add and pass a routing policy test that sandbox-only web-reverse backends are absent from default pools.
- [x] Add and pass a routing regression that `route()` does not import/use `fc_caller` on ordinary requests.
- [x] Track `session_memory/prompt_recall.py` and add a repo manifest regression for runtime dependency tracking.
- [x] Add and pass an identity-filter regression preserving third-party factual statements.
- [x] Run compileall, full pytest, `git diff --check`, then update status docs.

## Deployment Policy

Local-only until full pytest is green and a separate deployment plan is approved.
