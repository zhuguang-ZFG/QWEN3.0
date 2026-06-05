# LiMa Productivity Infrastructure Review

> Date: 2026-05-25
> Scope: LiMa Server, LiMa (`deepcode-cli`), and ESP32 (`esp32S_XYZ`).
> Goal: turn existing capabilities into real production usefulness, not
> feature spectacle.

## Product Constraint

All LiMa work must serve real productivity, productization, and LiMa's own
distinctive character. Favor reliability, observability, execution closure,
operator feedback, and useful delivery loops over decorative or speculative
features.

## Current Read

LiMa already has many strong building blocks: Redis-backed Device Gateway HA,
typed memory, mastery loop, eval registry, agent/tool governance, MCP access
plane, LiMa worker commands, and fake U8 smoke tests. The remaining
weakness is not "missing more ideas"; it is the gap between interfaces and a
daily-use production loop.

Current P0 status as of 2026-05-25:

| ID | Status |
|---|---|
| PROD-003 | ESP32 firmware compile passed; hardware flash is next. |
| PROD-004 | Path pipeline implemented: stroke font, SVG parser, preview, safety clamps. |
| PROD-005 | Intent parser upgraded with regex, confidence, rejection reasons, and gated LLM replanning. |
| PROD-006 | LiMa artifact bundle implemented under `.lima/artifacts/<task_id>/` for plan/test/review/ship. |
| PROD-007 | Ops metrics endpoint deployed and smoke-verified. |
| PROD-008 | Learning loop remains architecture-level follow-up. |

The highest leverage path is:

1. make ESP32 tasks observable, stateful, and hard to silently lose;
2. make Device Gateway turn intent into real executable geometry/G-code, not
   placeholders;
3. make LiMa produce reviewable plan/patch/test/ship artifacts from real
   context;
4. connect logs, memory, routing, prompts, and evals into one learning loop.

## Findings

| ID | Priority | Area | Evidence | Risk | Needed Outcome |
|---|---:|---|---|---|---|
| PROD-001 | P0 | ESP32 execution loop | `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/common/board.cc` default `HandleMotionTaskJson()` is empty; only the zhuguang board has a concrete motion handler. | Unsupported boards can receive a task and do nothing, which is worse than a clear failure. | Every supported board emits accepted/running/done/failed or explicit unsupported failure events. |
| PROD-002 | P0 | ESP32 failure telemetry | The zhuguang handler logs unsupported capability and missing `run_path` payload but returns without a failure event. | Server/Device Gateway can believe a task is still pending or silently lost. | Missing path, unsupported capability, bad params, U1 unavailable, and update-in-progress all return structured failure events with codes. |
| PROD-003 | P0 | Device intelligence | `device_gateway/tasks.py` maps `write_text` to a rectangle and `draw_generated` to a hardcoded star. | Voice "write/draw" demos look alive but do not produce useful real-world output. | Add a real text/vector/path pipeline with preview, safety limits, and fake-device replay before more protocol families. |
| PROD-004 | P0 | Intent understanding | `device_gateway/intent.py` is deterministic first-slice mapping. | Real commands beyond tiny Chinese/English phrases collapse to text-writing fallback. | Introduce a gated model-backed planner or grammar+LLM hybrid that outputs validated motion intents with reasons and rejected-command explanations. |
| PROD-005 | P0 | LiMa productivity | `/lima plan` creates a local task whose runner only echoes constraints; `/lima test` runs commands; `/lima ship` reviews diff only. | Commands exist, but do not yet behave like a productive implementation assistant. | Stage artifacts: context packet, implementation plan, patch proposal, test evidence, risks, rollback notes, and Server submission link. |
| PROD-006 | P1 | Observability surface | `observability/events.py` and `observability/metrics.py` exist, but `routes/system_endpoints.py` exposes health/status, not a focused operator metrics endpoint. | Good events stay hidden during incidents and joint debugging. | Add authenticated `/v1/ops/metrics` or admin panel slices for request_id/task_id/device_id/session_id correlation. |
| PROD-007 | P1 | Request correlation | Current observability wiring emits backend/route/quality events, but request start/end integration is not clearly universal. | Latency and failure analysis are fragmented across logs, task states, and route metrics. | Standardize correlation ids across chat, worker, Device Gateway, LiMa audit, and ESP32 motion events. |
| PROD-008 | P1 | Memory learning loop | Memory taxonomy and recall exist, but production outcomes are not yet clearly fed back into prompt/routing decisions. | Long-term memory can become a passive archive instead of improving work quality. | Promote verified lessons from failures, tests, and successful patches into typed memory and route/prompt eval queues. |
| PROD-009 | P1 | Prompt capability | LiMa has a hardcoded system prompt and templates, but no prompt registry/version/eval loop tied to outcomes. | Prompt improvements are hard to compare, roll back, or personalize safely. | Add prompt versions, fixture evals, and per-workflow prompt profiles for plan/patch/review/test/device. |
| PROD-010 | P1 | Routing intelligence | Router/eval primitives exist, but route decisions are still mostly pool/order/evidence rules. | It can choose a working model, but not yet learn task-fit from real LiMa outcomes. | Add task-outcome feedback: model, route reason, test result, review status, latency, cost, and failure class. |
| PROD-011 | P1 | Visualization | Device fake loop verifies protocol frames, but there is no first-class path preview/simulator/dashboard as the operator's daily view. | Hardware work remains blind and risky. | Add SVG/path preview, task replay, and simple device dashboard before camera/OCR/voice expansion. |
| PROD-012 | P2 | Maintainability | Large files remain in Server, LiMa, and ESP32 firmware. | Future fixes are slower and riskier. | Split only along production boundaries: task execution, prompt context, device motion executor, and ops views. |

## P0 Plan: Make The System Useful Under Hands

### P0.1 ESP32 Motion Executor Contract

- Add a shared U8 motion-task result helper so every return path emits one of:
  `accepted`, `running`, `progress`, `done`, `failed`.
- Add explicit error codes:
  `E_UNSUPPORTED_CAPABILITY`, `E_MISSING_PATH`, `E_BAD_PARAMS`,
  `E_U1_UNAVAILABLE`, `E_DEVICE_UPDATING`, `E_EXECUTION_FAILED`.
- Make default board behavior fail loudly instead of no-op for motion tasks.
- Add fake-U8 and firmware-side tests/smokes where the toolchain allows it.

Exit: a missing/unsupported motion task is visible in Server task state within
one smoke run.

### P0.2 Real Path/Text/Drawing Pipeline

- Replace rectangle/star placeholders with a small LiMa-owned path pipeline:
  intent -> vector/text layout -> normalized path -> safety validator -> preview
  -> U8 task.
- Start with deterministic text rendering or SVG-to-path/G-code adapter before
  any model-generated art.
- Save the preview artifact and source prompt on the task record, redacted when
  needed.
- Keep hardware allowlists and feed/point/size limits fail-closed.

Exit: "write LiMa" and one simple imported SVG can be previewed, sent to fake
U8, and replayed with identical task ids and events.

### P0.3 LiMa Work Artifact Bundle

- Upgrade `/lima plan` from echo mode to a real context packet:
  git diff, recent files, tests, AGENTS rules, open risks, and suggested slice.
- Add a local artifact directory per run with:
  `plan.md`, `context.json`, `tests.json`, `diff.patch`, `risks.md`,
  `ship.md`.
- Make `/lima ship` verify the artifact bundle instead of only raw diff.
- Keep deploy/push disabled unless a gated Server task explicitly asks for it.

Exit: one LiMa command produces a review packet that a human or Server can
consume without reading the whole terminal scrollback.

## P1 Plan: Make It Learn And Operate

### P1.1 Unified Operator Telemetry

- Add an authenticated metrics/status endpoint that joins:
  request ids, backend route, quality result, worker task, Device Gateway task,
  device id, motion event phase, and latest error class.
- Add CLI/status output for the same snapshot.
- Keep raw prompts, keys, paths, and device tokens redacted.

Exit: during a failed joint debug, one command answers: what task, which model,
which worker, which device, where it stopped, and what to do next.

### P1.2 Prompt And Routing Feedback

- Add prompt profile ids for chat/code-plan/code-patch/code-review/device-plan.
- Record outcome feedback:
  tests passed, review status, model, route reason, latency, failure class,
  and task type.
- Promote only verified lessons into memory and routing candidates.

Exit: a repeated class of failure changes future prompt/routing behavior only
after eval evidence, not by ad hoc prompt edits.

### P1.3 LiMa Real Worker Loop

- Move from "local stage commands" to an operator-safe work loop:
  claim task -> build context -> propose plan -> apply patch only when allowed
  -> test -> summarize -> submit -> retain artifact bundle.
- Add retry/quarantine reasons that are visible from Server.
- Add a narrow "fix test failure" workflow before broad autonomous coding.

Exit: LiMa can fix a small real repo issue end-to-end with reviewable
evidence and no hidden permission expansion.

## P2 Plan: Make It Pleasant, Distinctive, And Productized

### P2.1 Hardware Visualization

- Add task preview and replay pages for path, bounding box, feed, point count,
  event timeline, and failure reason.
- Add fake-device and real-device tabs only after auth and token boundaries are
  clear.

### P2.2 Drawing And Multimodal Growth

- After the motion path pipeline is reliable, add controlled drawing:
  SVG import, bitmap trace, text layout, and later model-generated vector
  planning.
- Keep display/audio/speech/OCR/camera/perception families gated until motion
  proves useful.

### P2.3 Codebase Shape

- Split large files incrementally where the split directly improves production
  work:
  Server request lifecycle, LiMa session/workflow, ESP32 motion executor,
  and zhuguang board motion helpers.

## First Slice Recommendation

Start with P0.1 + P0.2, not UI polish. The fastest route to real usefulness is
to make a voice or typed device command produce an observable, previewable,
replayable hardware task that either executes or fails with a precise reason.

Suggested first implementation sequence:

1. Server tests for `draw_generated` and `write_text` preview artifacts.
2. Device Gateway path pipeline module with deterministic text/SVG fixture.
3. Fake-U8 replay test for success and failure events.
4. ESP32 zhuguang failure-event hardening for missing path and unsupported
   capability.
5. VPS fake-device smoke, then gated real-device smoke.

## Verification Rules

- For Server changes: focused pytest first, then broader gateway/agent subset.
- For LiMa changes: `npm.cmd run check`, focused tests, then
  `npm.cmd test`.
- For ESP32 changes: compile where available, fake-U8 smoke always, real-device
  smoke only with explicit token/device readiness.
- For VPS validation: backup, scoped deploy, restart, health, public smoke,
  rollback evidence, and progress/finding update.
