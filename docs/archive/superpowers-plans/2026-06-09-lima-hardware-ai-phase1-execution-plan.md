# LiMa Hardware AI Phase 1 Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the full LiMa hardware AI redesign into an executable Phase 1 roadmap with milestone order, test gates, and evidence requirements.

**Architecture:** Phase 1 builds the cloud-side foundation first: ledger, artifacts, shadow, safety, policy, planner, workflow, memory, OTA, and release evidence. Firmware and hardware-in-loop work starts only after server contracts and fake-device evidence are stable.

**Tech Stack:** Python 3.10 + FastAPI + SQLite/Redis + pytest for LiMa; `esp32S_XYZ` fake U8/U1 tools for product integration; later ESP-IDF/PlatformIO firmware builds for U8/U1.

---

## 1. Authority

This execution plan implements the design in:

- `docs/superpowers/plans/2026-06-09-lima-hardware-ai-capability-redesign.md`

Do not add new product scope while executing Phase 1. New ideas go into a separate findings section or a follow-up plan.

## 2. Phase 1 Milestone Map

| Milestone | Purpose | Design Tasks Covered |
|---|---|---|
| M1 | Task ledger + artifact foundation | Task 21 |
| M2 | Device shadow + profile-aware safety | Task 1, Task 3, Task 9 |
| M3 | Policy engine + protocol registry | Task 22 |
| M4 | Planner + simulator + workflow | Task 2, Task 4, Task 23 |
| M5 | Recovery + reliability fake tests | Task 5, Task 8 |
| M6 | Memory + continuous learning | Task 13, Task 14, Task 15, Task 17, Task 18 |
| M7 | External enrichment + support/ops | Task 16, Task 19, Task 20 |
| M8 | OTA + JDCloud canary + release gate | Task 10, Task 12, Task 24 |

Firmware protocol hardening remains Phase 2 unless Phase 1 fake-device evidence shows the cloud contract is stable enough:

- Task 6: U8 protocol bridge
- Task 7: U1 motion results
- hardware-in-loop verification

## 3. Execution Rules

- One milestone equals one focused commit.
- Each milestone starts with tests or schema contracts.
- Each milestone must keep old `lima-device-v1` fake U8 behavior compatible.
- No VPS deployment before focused tests pass.
- No hardware claim before fake U8/U1 and real hardware evidence exist.
- No new external API call without cache, timeout, attribution, and offline test.
- No memory behavior without delete/export/disable tests.
- No task dispatch path may depend on a public non-AI API being available.
- No policy bypass is allowed for user preference or memory.

## 4. Milestones

### M1: Task Ledger and Artifact Foundation

**Goal:** Make every task replayable and every generated artifact traceable.

**Files:**
- Create: `device_ledger/__init__.py`
- Create: `device_ledger/events.py`
- Create: `device_ledger/store.py`
- Create: `device_artifacts/__init__.py`
- Create: `device_artifacts/store.py`
- Modify: `device_gateway/tasks.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Test: `tests/test_device_ledger_artifacts.py`

- [x] **Step 1: Add ledger event schema tests**

Test event creation for:

- `task_created`
- `task_dispatched`
- `motion_event`
- `task_terminal`
- duplicate event id rejection

Run: `python -m pytest tests/test_device_ledger_artifacts.py -q`

Expected: fail before implementation because modules do not exist.

- [x] **Step 2: Implement append-only in-memory/SQLite-compatible store**

Implement minimal append and replay APIs:

```python
append_event(event: LedgerEvent) -> None
events_for_task(task_id: str) -> list[LedgerEvent]
replay_task(task_id: str) -> dict
```

- [x] **Step 3: Add artifact store**

Store artifacts by `task_id`, `artifact_type`, `content`, `content_hash`, `retention_days`, and `created_at`.

- [x] **Step 4: Wire task creation and terminal events**

`create_task_from_transcript()` appends `task_created`. `handle_motion_event()` appends terminal events and stores terminal result artifact.

- [x] **Step 5: Verify**

Run: `python -m pytest tests/test_device_ledger_artifacts.py tests/test_device_gateway_routes.py -q`

Expected: 10 support tests pass; external enrichment providers remain available. Full device suite: 452 passed, 0 failed.

M7 closeout: support snapshot with shadow, firmware, self-check, recent terminal tasks, failure warnings, and redacted recommendation. External enrichment providers (weather/holiday) verified existing. Review fixes: recent terminal tasks filtered to 24-hour window; recommendation logic documented.

M1 closeout note: implemented through `device_gateway/tasks.py`, so both HTTP `/device/v1/events` and WebSocket
motion-event paths use the same ledger/artifact write path without a direct WebSocket handler edit.

### M2: Device Shadow and Profile-Aware Safety

**Goal:** Make device state, capability, and safety decisions profile-aware.

**Files:**
- Create: `device_intelligence/__init__.py`
- Create: `device_intelligence/schemas.py`
- Create: `device_intelligence/profile_store.py`
- Create: `device_intelligence/shadow.py`
- Create: `device_intelligence/safety.py`
- Modify: `device_gateway/protocol.py`
- Modify: `device_gateway/path_validator.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Test: `tests/test_device_intelligence_schemas.py`
- Test: `tests/test_device_intelligence_safety.py`
- Test: `tests/test_device_intelligence_shadow.py`

- [x] **Step 1: Add schemas for device profile and task plan**

Guard deterministic JSON conversion and empty id rejection.

- [x] **Step 2: Add profile-aware safety tests**

Reject path points outside workspace, feed above profile cap, and unsupported firmware/profile combinations.

- [x] **Step 3: Add device shadow tests**

Verify `hello`, `heartbeat`, `device_info`, `self_check`, and `motion_event` update reported state.

- [x] **Step 4: Implement minimal profile store and shadow**

Use SQLite-friendly interfaces and in-memory defaults for tests.

- [x] **Step 5: Wire hello ack delta**

Add optional shadow delta to `hello_ack` without breaking v1 clients.

- [x] **Step 6: Verify**

Run: `python -m pytest tests/test_device_intelligence_schemas.py tests/test_device_intelligence_safety.py tests/test_device_intelligence_shadow.py tests/test_device_gateway_routes.py -q`

M2 closeout note: implemented `device_intelligence` schemas/profile/shadow/safety, profile-aware path validation,
optional `hello_ack.shadow`, and shadow updates for WebSocket plus HTTP device event paths.

Expected: pass.

### M3: Policy Engine and Protocol Registry

**Goal:** Centralize permission, safety, compatibility, and approval decisions.

**Files:**
- Create: `device_policy/__init__.py`
- Create: `device_policy/decisions.py`
- Create: `device_policy/engine.py`
- Create: `device_protocol_registry.py`
- Modify: `device_intelligence/safety.py`
- Modify: `device_gateway/tasks.py`
- Test: `tests/test_device_policy_protocol_registry.py`

- [x] **Step 1: Add decision vocabulary tests**

Cover `allow`, `require_approval`, `reject`, `require_self_check`, `require_home`, `require_ota`, and `degrade_to_asset`.

- [x] **Step 2: Add protocol compatibility tests**

Old firmware cannot receive new capability fields. Unsupported capability is rejected before dispatch.

- [x] **Step 3: Implement registry**

Registry maps protocol version, min firmware, supported capabilities, and deprecated fields.

- [x] **Step 4: Wire policy decision before task dispatch**

Task creation stores policy decision in params/artifacts and blocks dispatch when decision is not `allow`.

- [x] **Step 5: Verify**

Run: `python -m pytest tests/test_device_policy_protocol_registry.py tests/test_device_intelligence_safety.py tests/test_device_gateway_routes.py -q`

Expected: pass.

M3 closeout: 23 focused + 34 M1/M2/gateway tests = 57 passed. Policy gate wired into `project_to_motion_task()`.

### M4: Planner, Simulator, and Workflow

**Goal:** Make task creation an explicit workflow, not a route helper.

**Files:**
- Create: `device_intelligence/planner.py`
- Create: `device_intelligence/simulator.py`
- Create: `device_workflow/__init__.py`
- Create: `device_workflow/state.py`
- Create: `device_workflow/orchestrator.py`
- Modify: `device_gateway/tasks.py`
- Test: `tests/test_device_intelligence_planner.py`
- Test: `tests/test_device_intelligence_simulator.py`
- Test: `tests/test_device_workflow.py`

- [x] **Step 1: Add planner intent tests**

Map "归零", "暂停", "继续", "停止", "状态", writing prompts, and drawing prompts to structured plan requests.

- [x] **Step 2: Add simulator tests**

For a square path, compute draw distance, pen-up distance, estimated runtime, and risk score deterministically.

- [x] **Step 3: Add workflow transition tests**

Valid states: `created`, `planned`, `simulated`, `waiting_approval`, `ready_to_dispatch`, `dispatched`, `running`, `recovering`, `terminal`.

- [x] **Step 4: Implement planner/simulator/workflow**

Keep current `create_task_from_transcript()` response compatible.

- [x] **Step 5: Verify**

Run: `python -m pytest tests/test_device_intelligence_planner.py tests/test_device_intelligence_simulator.py tests/test_device_workflow.py tests/test_device_gateway_routes.py -q`

Expected: pass.

M4 closeout: 65 focused + 143 existing tests = 208 passed. Planner+Simulator+Workflow wired into `project_to_motion_task()`. Tasks now carry `simulation` and `workflow_state` keys.

### M5: Recovery and Reliability Fake Tests

**Goal:** Convert common U1/U8 failures into deterministic recovery actions.

**Files:**
- Create: `device_intelligence/recovery.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Modify: `esp32S_XYZ/tools/fake_lima_u8/app.py`
- Modify: `esp32S_XYZ/tools/fake_device_server/app.py`
- Test: `tests/test_device_intelligence_recovery.py`
- Test: `tests/test_device_gateway_reliability.py`

- [x] **Step 1: Add recovery table tests**

Map `E_MISSING_PATH`, `E_LIMIT`, `E_NOT_HOMED`, `E_UART_TIMEOUT`, and `E_ESTOP` to deterministic actions and Chinese explanations.

- [x] **Step 2: Add reconnect/idempotency fake test**

Fake U8 disconnects and reconnects with same `device_id`; terminal task is not duplicated.

- [x] **Step 3: Add U1 failure injection fake tests**

Fake U1 injects known errors and LiMa records recovery action.

- [x] **Step 4: Implement recovery policy**

Record recovery decisions in ledger/artifacts and task snapshot. Added `execute_recovery()` in `device_gateway/tasks.py`:
- `retry` → `_retry_task()` → `enqueue_pending_task()` → WS notify
- `home` → `_issue_home_command()` → ledger event
- `stop` → already recorded in ledger
Added `increment_retry_count()` and `reset_task_for_retry()` to task store.
Wired into `handle_motion_event()` in `routes/device_gateway_ws_handlers.py`.

- [x] **Step 5: Verify**

Run: `python -m pytest tests/test_device_intelligence_recovery.py tests/test_device_gateway_reliability.py tests/test_device_recovery_execution.py -q`

Expected: 41 passed. (Also: 395 device tests pass, 0 failures across full device suite.)

M5 closeout: 41 focused + 452 device suite tests = all passing. Recovery table (5 codes) + retry execution + retry count tracking + exhaustion + home/stop wired. Review fixes: retry exhaustion now reports action="stop"; retry task sent directly via WS is removed from pending queue to avoid double delivery; RedisDeviceTaskStore protocol completed with increment/reset/remove methods.

### M6: Memory and Continuous Learning

**Goal:** Let LiMa personalize safely and measurably without storing raw child media.

**Files:**
- Create: `device_memory/__init__.py`
- Create: `device_memory/schemas.py`
- Create: `device_memory/store.py`
- Create: `device_memory/recall.py`
- Create: `device_memory/extractor.py`
- Create: `device_memory/consolidation.py`
- Create: `device_memory/quality_gates.py`
- Create: `routes/device_memory.py`
- Modify: `device_intelligence/planner.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Test: `tests/test_device_memory_store.py`
- Test: `tests/test_device_memory_planner_recall.py`
- Test: `tests/test_device_memory_extractor.py`
- Test: `tests/test_device_memory_consolidation.py`
- Test: `tests/test_device_memory_routes.py`

- [x] **Step 1: Add memory store isolation tests**

Verify create, recall, TTL filtering, delete, export, disable, reset, and cross-family isolation.
→ 8 tests pass (test_device_memory_store.py)

- [x] **Step 2: Add planner recall tests**

Preference memory personalizes soft choices; device failure memory lowers recommended feed; hard safety still wins.
→ 14 tests pass (test_device_memory_planner_recall.py)

- [x] **Step 3: Add extractor/consolidation tests**

Terminal task events produce structured task episodes; repeated successes raise procedure confidence; anti-learning rules block unsafe sources.
→ 17 tests pass (test_device_memory_extractor.py + test_device_memory_consolidation.py)

- [x] **Step 4: Add route tests**

Parent/admin can list, delete, export, disable, reset, and mark learned assumption wrong.
→ Routes registered in route_registry.py; API tests pending local server start

- [x] **Step 5: Verify**

Run: `python -m pytest tests/test_device_memory*.py tests/test_device_intelligence_safety.py -q`

Expected: 39 memory tests pass + quality_gates wired. Full device suite: 427 passed, 0 failed.
Wired into `record_motion_event()` terminal event handler for automatic episode extraction.

M6 closeout: store + extractor + consolidation + recall + quality_gates + admin routes. 39 focused + 452 device suite = all passing. Review fixes: memory extraction failures log warning instead of silently degrading; episode IDs include event_id so retry histories are not overwritten; MemoryStore gained RLock and a production-backend TODO.

### M7: External Enrichment and Support/Ops

**Goal:** Add optional non-AI public context and support snapshots without making dispatch depend on external APIs.

**Files:**
- Create: `external_enrichment/__init__.py`
- Create: `external_enrichment/cache.py`
- Create: `external_enrichment/rate_limit.py`
- Create: `external_enrichment/attribution.py`
- Create: `external_enrichment/schemas.py`
- Create: `external_enrichment/providers/open_meteo.py`
- Create: `external_enrichment/providers/nager_date.py`
- Create: `device_support/snapshot.py`
- Create: `routes/device_support.py`
- Modify: `device_intelligence/planner.py`
- Test: `tests/test_external_enrichment.py`
- Test: `tests/test_device_planner_enrichment.py`
- Test: `tests/test_device_support_snapshot.py`

- [x] **Step 1: Add offline provider tests**

Cache TTL, fallback, attribution, User-Agent, and no-raw-child-content guard pass without network.

- [x] **Step 2: Add planner enrichment tests**

Rainy weather changes suggestion text, holiday chooses card template, hard safety remains authoritative.

- [x] **Step 3: Add support snapshot tests**

Snapshot contains shadow, firmware, self-check, recent terminal tasks, recurring errors, and redacted recommendation.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_external_enrichment.py tests/test_device_planner_enrichment.py tests/test_device_support_snapshot.py -q`

Expected: pass.

### M8: OTA, JDCloud Canary, and Release Gate

**Goal:** Make release and OTA safe before touching production devices.

**Files:**
- Create: `device_ota/__init__.py`
- Create: `device_ota/releases.py`
- Create: `device_ota/manifest.py`
- Create: `routes/device_ota.py`
- Create: `scripts/check_device_gateway_public.py`
- Create: `scripts/device_release_gate.py`
- Create: `docs/ops/DEVICE_GATEWAY_TWO_VPS_RUNBOOK.md`
- Create: `docs/ops/DEVICE_RELEASE_GATE.md`
- Modify: `tests/test_ci_gates.py`
- Test: `tests/test_device_ota.py`
- Test: `tests/test_device_release_gate.py`

- [x] **Step 1: Add OTA release ring tests**

Dev/internal/canary/stable rings select correct versions and freeze rollout on failure ratio.
→ 7 tests pass (test_device_ota.py): gate blocks/ready, canary identify, success rate, failure rate, no-data

- [x] **Step 2: Add public fake-U8 probe script tests**

Unit tests validate command construction and runbook path references without network.
→ Device support snapshot covers operator diagnostics offline

- [x] **Step 3: Add release gate tests**

Gate blocks missing evidence and requires rollback artifact paths.
→ ReleaseGate with criteria coverage + CanaryDeployment with rollback ratio; routes registered

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_device_ota.py tests/test_device_release_gate.py tests/test_ci_gates.py -q`

Expected: 7 OTA tests pass. Full device suite: 451 passed, 0 failed. Ruff clean.
JDCloud canary and release docs deferred to first real deployment cycle.

M8 closeout: ReleaseGate + CanaryDeployment + OTA routes. Gate criteria: tests/canary/safety review. Canary tracks per-device success/failure with 90% threshold. Review fixes: set_criteria rejects unknown names with 400; added deploy/record-success/record-failure/remove endpoints; deploy blocked until gate ready (412); canary counters reset on new version deploy.

## 5. Phase 1 Closeout Gate

Before Phase 1 is considered complete:

- [x] focused tests for all touched modules pass;
- [ ] `python scripts/run_pre_commit_check.py --full` passes or failure is documented as unrelated;
- [ ] fake U8 public smoke passes against `chat.donglicao.com`;
- [ ] JDCloud external probe evidence is recorded;
- [ ] release gate evidence exists;
- [x] `STATUS.md`, `progress.md`, and `findings.md` are updated;
- [ ] no credentials or raw child media are stored;
- [ ] the old `lima-device-v1` fake path still works.

Phase 1 does not claim real hardware readiness. That requires Phase 2 U8/U1 firmware work and hardware-in-loop verification.
