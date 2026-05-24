# LiMa TechSpar-Inspired Mastery Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for implementation phases, `superpowers:verification-before-completion` before marking a phase done, and `safety-guard` before any autonomous runner, tool execution, GitHub operation, VPS deployment, or data migration.
>
> **Current status:** Implementation has started and the local Phase 0-5 slice is complete: `mastery_loop/` contains typed records, SQLite-backed storage, event adapters, scoring, weak-point extraction, review scheduling, recommendations, and traces. Phase 7's promotion gate is also wired: agent skill promotion requires mastery evidence. Admin UI exposure and hot-path planner/routing influence remain gated future work.

**Goal:** Borrow TechSpar's continuous training loop idea and adapt it into LiMa's coding-agent improvement loop: every coding task, review, test failure, deployment event, and routing lesson should update a durable project/module capability profile that influences future planning, retrieval, testing, and self-improvement.

**Source reference:**

- TechSpar repository: https://github.com/AnnaSuSu/TechSpar
- Current README describes TechSpar as a technical interview loop that connects focused training, resume interview, JD preparation, real-time copilot, and recording review through the same long-term memory, profile update, mastery, and next-round scheduling system.
- License: `CC BY-NC 4.0`. Borrow concepts only; do not copy code into LiMa without a separate license review.

---

## Strategic Fit For LiMa

TechSpar is not primarily useful as an agent framework. Its value is the feedback loop:

```text
training / interview / copilot / review
  -> per-question scoring
  -> weak-point extraction
  -> mastery update
  -> long-term profile update
  -> SM-2 review scheduling
  -> next training round becomes more targeted
```

LiMa can translate that into:

```text
coding request / code review / test run / deploy / incident
  -> per-task scoring
  -> weak module and failure-pattern extraction
  -> project/module mastery update
  -> agent behavior profile update
  -> review and regression scheduling
  -> next plan/test/retrieval route becomes more targeted
```

This fills a gap between:

- `docs/REFERENCE_PROJECT_EVALUATION.md`: evidence retrieval and always-on memory.
- `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md`: agent workbench, skill/gene evolution, and approval gates.

TechSpar contributes the "mastery profile and next-round scheduling" layer between memory and autonomy.

---

## Borrow / Do Not Borrow

| TechSpar idea | LiMa value | Recommended adaptation |
|---|---:|---|
| Shared long-term profile across product modes | Very high | One project/module/agent profile shared by chat, IDE, review, tests, and deploy workflows. |
| Dynamic question generation from knowledge, history, weak points, and mastery | High | Dynamic test/review focus from recent failures, fragile modules, and low-confidence routes. |
| Training result writes back to profile | Very high | Every successful or failed coding task updates module stability, failure patterns, and lessons. |
| Per-question scoring | High | Per-task and per-module scoring for correctness, test coverage, review severity, deploy risk. |
| Weak-point extraction | Very high | Track fragile files, repeated bug classes, missing tests, risky providers, and agent behavior issues. |
| SM-2 review scheduling | Medium-high | Schedule future regression checks and memory refresh for risky modules. |
| Graph of related weak points | Medium-high | Build a lightweight module/failure graph for admin diagnostics. |
| Interview Copilot UI and voice stack | Low | Not relevant to LiMa's current private coding assistant direction. |
| React interview product shell | Low | Do not copy; LiMa needs backend/admin trace first. |

---

## Target Architecture

```text
LiMa event sources
  - chat/completions
  - Anthropic messages
  - code review
  - pytest/compile output
  - deployment smoke
  - routing failure
  - tool gateway audit
  - agent workbench run

        |
        v
mastery_loop/
  event_adapter.py       # normalize raw events
  scorer.py              # score task/module/backend outcomes
  weak_point_extractor.py# extract fragile files, missing tests, failure classes
  profile_store.py       # SQLite-backed profile and mastery records
  scheduler.py           # SM-2-inspired regression/review scheduling
  recommender.py         # suggest next tests/retrieval/review focus
  trace.py               # explain why a recommendation exists

        |
        v
future integrations
  - retrieval injector
  - agent planner
  - tester agent
  - memory/evolution agent
  - admin trace UI
```

Keep the first implementation local, SQLite-backed, and opt-in. No new frontend is needed for Phase 1.

---

## Data Model

Suggested records:

```text
MasteryEvent
  id
  source              # test, review, deploy, route, tool, agent
  project
  files
  modules
  outcome             # success, fail, flaky, blocked
  score
  severity
  evidence_ref
  created_at

ModuleMastery
  project
  module
  stability_score
  test_confidence
  review_risk
  deploy_risk
  last_seen_at
  next_review_at

WeakPoint
  project
  kind                # missing_test, brittle_route, auth_risk, prompt_gap, flaky_backend
  file_or_module
  description
  severity
  recurrence_count
  last_evidence_ref
  status              # open, improving, resolved, ignored

AgentBehaviorSignal
  role
  task_id
  behavior            # over-edit, missed-test, bad-assumption, good-fix, strong-review
  score_delta
  evidence_ref

ReviewSchedule
  target_type         # module, weak_point, backend, skill
  target_id
  interval_days
  ease_factor
  due_at
  reason
```

---

## Phase 0: Reference Notes And Boundary

**Files:**

- Create: `docs/reference/TECHSPAR_BORROWING_NOTES.md`
- Update: `docs/DOCUMENTATION_STATUS.md`
- Update: `findings.md`
- Update: `progress.md`

**Steps:**

- [x] Record TechSpar concepts borrowed for LiMa: long-term profile, weak-point extraction, mastery update, review scheduling, dynamic next-round focus.
- [x] Record rejected areas: interview UI, voice stack, resume/JD business logic, user-facing React product shell.
- [x] Record license boundary: concept borrowing only because TechSpar uses CC BY-NC 4.0.
- [x] Run a docs secret scan:

```powershell
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT\docs\reference\TECHSPAR_BORROWING_NOTES.md D:\GIT\docs\superpowers\plans\2026-05-23-techspar-mastery-loop.md
```

**Exit criteria:**

- TechSpar is documented as a mastery-loop reference, not an agent runtime dependency.
- No credential-like strings appear in the new docs.

**Status:** Complete in `docs/reference/TECHSPAR_BORROWING_NOTES.md`.

---

## Phase 1: Mastery Store Skeleton

**Purpose:** Add the durable profile store before using it in routing or agents.

**Implemented module:**

```text
mastery_loop/
  __init__.py
  models.py
  profile_store.py
```

**Tests to write first:**

- Create and fetch `ModuleMastery`.
- Append `MasteryEvent`.
- Add/update `WeakPoint` recurrence count.
- No event stores raw secrets or full prompt payloads.

**Implementation notes:**

- Use SQLite, matching LiMa's current memory direction.
- Keep profiles project-scoped.
- Store evidence references and short summaries, not full logs.
- Do not modify routing behavior yet.

**Exit criteria:**

- LiMa can record profile and weak-point data locally.
- Existing target suite still passes.

**Status:** Complete in `mastery_loop/models.py` and `mastery_loop/profile_store.py`.

---

## Phase 2: Event Adapters

**Purpose:** Convert existing LiMa evidence into normalized mastery events.

**Implemented module:**

```text
mastery_loop/
  event_adapter.py
```

**Initial event sources:**

- Test results from planned verification commands.
- Code review findings from agent/reviewer output.
- Deployment smoke results.
- Routing failure classes from `health_tracker.py`.
- Tool Gateway audit summaries.
- Session Memory compaction summaries where relevant.

**Tests:**

- Pytest failure output becomes a `test` event with failed file/module hints.
- Review finding becomes a `review` event with severity.
- Routing quota/auth/manual-refresh failure becomes a `route` weak point.
- Tool Gateway blocked execution becomes a `tool` risk signal.

**Exit criteria:**

- Existing runtime evidence can feed the mastery store without changing hot-path behavior.

**Status:** Complete in `mastery_loop/event_adapter.py`.

---

## Phase 3: Scoring And Weak-Point Extraction

**Purpose:** Turn raw events into useful signals.

**Implemented modules:**

```text
mastery_loop/
  scorer.py
  weak_point_extractor.py
```

**Scoring dimensions:**

- Correctness: tests pass/fail, exact-output smoke, compile results.
- Coverage confidence: whether relevant tests exist and ran.
- Review risk: P0/P1/P2 findings.
- Deployment risk: smoke, rollback, restart health.
- Routing reliability: backend health, latency, failure class.
- Agent behavior: over-editing, missing tests, bad assumptions, strong fixes.

**Tests:**

- P0/P1 review finding lowers module stability.
- Repeated failure increases weak-point recurrence.
- Successful verified fix improves stability but does not erase history.
- Flaky backend/routing failures affect backend confidence, not unrelated module scores.

**Exit criteria:**

- LiMa can explain "this module is risky because..." from local evidence.

**Status:** Complete in `mastery_loop/scorer.py` and `mastery_loop/weak_point_extractor.py`.

---

## Phase 4: SM-2-Inspired Review Scheduler

**Purpose:** Borrow TechSpar's review scheduling idea for code quality.

**Implemented module:**

```text
mastery_loop/
  scheduler.py
```

**Adaptation:**

- High-risk modules get shorter review intervals.
- Repeated successful checks increase interval.
- New P0/P1 findings reset interval.
- Stale critical modules become due for regression review.

**Tests:**

- Failed check schedules near-term review.
- Repeated success stretches interval.
- P0 finding resets due date to soon.
- Ignored weak point does not keep scheduling unless reopened.

**Exit criteria:**

- LiMa can list due regression/review targets.

**Status:** Complete in `mastery_loop/scheduler.py`.

---

## Phase 5: Planner And Tester Recommendations

**Purpose:** Make mastery data influence agent behavior safely.

**Implemented modules:**

```text
mastery_loop/
  recommender.py
  trace.py
```

**Recommendations:**

- Suggested tests for a planned change.
- Files/modules requiring extra review.
- Backends/routes requiring smoke.
- Memories or reference docs to recall.
- Weak points that should be checked before completion.

**Integration targets:**

- Planner Agent from `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md`.
- Tester Agent.
- Retrieval injector trace.

**Tests:**

- A change touching risky module recommends focused tests.
- A recent deployment incident recommends smoke checks.
- A repeated auth issue recommends access-guard tests.
- Recommendation includes trace evidence and does not include secrets.

**Exit criteria:**

- LiMa planning becomes evidence-weighted without forcing automatic code changes.

**Status:** Complete in `mastery_loop/recommender.py` and `mastery_loop/trace.py`.

---

## Phase 6: Admin Trace And Weak-Point View

**Purpose:** Make the loop visible before letting it drive more autonomy.

**Future admin views:**

- Module mastery table.
- Open weak points.
- Due review schedule.
- Recent events.
- Recommendation trace.
- Agent behavior signals.

**Rules:**

- Admin routes must remain private.
- Do not expose raw secrets, full prompts, API keys, VPS credentials, or local private paths.
- Query-token login hardening should be completed before showing sensitive mastery data broadly.

**Exit criteria:**

- Owner can see what LiMa thinks is risky and why.

**Status:** Deferred and gated. The local recommendation/trace layer exists; broad admin UI exposure requires private admin guard hardening and focused tests.

---

## Phase 7: Close The Learning Loop

**Purpose:** Connect mastery loop with skill/gene evolution.

**Integration with `agent_evolution`:**

- A skill/gene candidate must include recent mastery evidence.
- Failed or flaky tasks cannot auto-promote a skill.
- A promoted skill should improve or stabilize future mastery scores.
- Rollback or rejection should create a mastery event.

**Tests:**

- Candidate from failed task is rejected.
- Candidate from successful verified task is suggestion-only until approved.
- Promotion writes an event and next-review schedule.

**Exit criteria:**

- LiMa can improve its workflow from evidence, not vibes.

**Status:** Promotion gate is wired in `agent_evolution.promote_candidate()` and `/agent/skills/{skill_id}/promote`: eval pass, manual approval, and non-empty mastery evidence refs are required. Automatic event writes from promotion remain future gated work.

---

## Verification Gate

Before any implementation phase is marked complete:

```powershell
git -C D:\GIT diff --check
D:\GIT\venv\Scripts\python.exe -m py_compile <touched-python-files>
D:\GIT\venv\Scripts\python.exe -m pytest <new-or-focused-tests> -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest tests .\test_routing_engine.py .\test_rate_limiter.py .\test_http_caller.py .\test_dual_track.py .\test_code_orchestrator.py .\test_streaming.py .\test_skills_injector.py --ignore=active_model
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT
```

Do not describe the target suite as unrestricted full-repo pytest. This workspace contains unrelated reference repositories and generated trees.

---

## Success Criteria

This TechSpar-inspired layer is successful when:

- LiMa remembers which modules and workflows are fragile.
- Test and review plans are chosen from evidence, not only static defaults.
- Repeated failures become explicit weak points with recurrence counts.
- Successful verified fixes improve mastery scores but keep audit history.
- Agent self-improvement candidates require mastery evidence before promotion.
- The owner can inspect and override the system's risk model.

At that point, LiMa is no longer merely routing requests or storing memories. It has a measurable improvement loop: evidence comes in, profile changes, next work becomes sharper.
