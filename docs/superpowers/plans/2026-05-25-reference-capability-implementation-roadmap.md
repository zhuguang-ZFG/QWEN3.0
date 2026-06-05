# Reference Capability Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the external reference-project learning into LiMa-native,
tested, reversible implementation slices without copying or mass-installing
reference projects.

**Architecture:** Keep the existing LiMa Server, LiMa, and `esp32S_XYZ`
ownership boundaries. Every adopted idea lands behind a LiMa-owned interface,
small tests, documentation evidence, and an explicit gate for license,
security, privacy, cost, and rollback.

**Tech Stack:** Python/FastAPI/SQLite/Redis for LiMa Server, TypeScript for
LiMa, ESP32 firmware/product code in `esp32S_XYZ`, pytest/npm tests,
systemd/nginx/VPS smoke scripts, and markdown status records.

---

## Source Documents

- `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`
- `docs/reference/LIMA_10_SUBSYSTEM_OPEN_SOURCE_RECOMMENDATIONS.md`
- `docs/reference/MCP_CONNECTOR_CATALOG.md`
- `docs/reference/AI_ENGINEERING_COMPETENCY_MAP_2026.md`
- `docs/reference/HARDWARE_COMPANION_REFERENCES.md`
- `docs/REFERENCE_PROJECT_EVALUATION.md`
- `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`

## Operating Rules

- Do not replace LiMa's router, key custody, memory store, worker gates, or
  Device Gateway with an external framework wholesale.
- Do not add GPL/AGPL/no-license code as a runtime dependency.
- Treat MCP connectors as authority-bearing access paths, not prompts.
- Treat Skills as methods and review playbooks; they do not grant permissions.
- Treat hardware, voice cloning, messaging, browser scraping, cloud control,
  finance/trading, and production deploy actions as gated surfaces.
- Every implementation slice must include tests, docs, rollback notes, and a
  verification command recorded in `progress.md`.

## Phase 0 - Device Gateway HA Reliability Closure

**Status:** Implemented locally after review.

**Files:**
- Modify: `device_gateway/redis_store.py`
- Modify: `device_gateway/store.py`
- Modify: `device_gateway/tasks.py`
- Modify: `device_gateway/notifier.py`
- Modify: `routes/device_gateway.py`
- Modify: `requirements_server.txt`
- Test: `tests/test_device_gateway_redis_store.py`
- Test: `tests/test_device_gateway_routes.py`
- Docs: `STATUS.md`
- Docs: `progress.md`
- Docs: `docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md`

- [x] Add Redis pending-to-processing queue movement with `LMOVE`.
- [x] Add `ack_processing_task(device_id, task_id)` and call it from HTTP and
  WebSocket `motion_event` handlers.
- [x] Remove processing entries by matching the full queued task payload by
  `task_id`.
- [x] Base stale recovery on `processing_started_at`, not pending enqueue time.
- [x] Remove processing entries before requeueing send failures or disconnect
  outstanding tasks.
- [x] Add notifier exception isolation and health state.
- [x] Degrade publish failure to queued response instead of HTTP 500.
- [x] Add `redis>=5.0` to `requirements_server.txt`.
- [x] Verify focused Device Gateway suite: `35 passed`.
- [x] Verify agent/device subset: `49 passed`.

## Phase 1 - Reference Implementation Ledger

**Status:** Implemented as `docs/REFERENCE_IMPLEMENTATION_LEDGER.md`.

**Purpose:** Make it impossible to confuse "reference admitted" with
"implemented".

**Files:**
- Create: `docs/REFERENCE_IMPLEMENTATION_LEDGER.md`
- Modify: `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`
- Modify: `docs/reference/LIMA_10_SUBSYSTEM_OPEN_SOURCE_RECOMMENDATIONS.md`
- Modify: `docs/REFERENCE_PROJECT_EVALUATION.md`
- Modify: `docs/DOCUMENTATION_STATUS.md`

- [x] Add a ledger table with columns: reference, status, LiMa subsystem,
  implementation files, and evidence.
- [x] Normalize statuses to `concept`, `planned`, `implementing`,
  `implemented`, `gated`, `evaluating`, and `rejected`.
- [x] Mark currently implemented slices: backend routing, context retrieval,
  typed memory daemon, mastery-related memory promotion, agent/tool gates,
  Device Gateway Redis HA, dev-search MCP tools, streaming events, data
  workbench, provider automation, and online smoke-adjacent evidence.
- [x] Mark gated slices: tree-sitter adapter, LEANN adapter, observability
  exporters, MCP Python SDK surface, sandbox provider, and broad external
  connectors.
- [x] Verify with ledger status counting and doc checks.
- [x] Record the follow-up shape for later: expand the ledger into
  `docs/reference/` or add per-capability owner/next-gate columns only when
  Phase 2 needs that extra ownership detail.

## Phase 2 - Code Intelligence And Retrieval

**References:** OpenRAG, LightRAG, GraphRAG, rerankers, tree-sitter,
Sirchmunk, claude-context, graphify, code-review-graph.

**Files:**
- Modify: `code_context/*`
- Modify: `context_pipeline/*`
- Test: `tests/test_code_context*.py`
- Test: `tests/test_context_pipeline*.py`
- Docs: `docs/reference/REFERENCE_IMPLEMENTATION_LEDGER.md`

- [x] Confirm the single authoritative retrieval injection path and remove or
  quarantine duplicate prompt-context paths.
- [x] Add a LiMa-owned graph/vector index protocol with in-memory fixtures.
- [x] Add a reranker interface that can run with deterministic local fixtures
  before any hosted or model-backed reranker is admitted.
- [x] Add source-quality scoring fields to retrieval traces.
- [x] Add a narrow optional type/static-analysis lane for stable Python modules
  before expanding to the repo.
- [x] Verify retrieval fixture tests and record selected files/chunks plus why
  they were injected.

## Phase 3 - Memory And Mastery

**References:** Google always-on-memory-agent, stash, hindsight, Mem0, Letta,
Zep, TechSpar, RuVector.

**Files:**
- Modify: `session_memory/*`
- Modify: `mastery_loop/*`
- Test: `tests/test_session_memory*.py`
- Test: `tests/test_mastery_loop*.py`
- Docs: `docs/REFERENCE_PROJECT_EVALUATION.md`
- Docs: `docs/reference/REFERENCE_IMPLEMENTATION_LEDGER.md`

- [x] Normalize memory kinds: `user_pref`, `project_fact`, `code_fact`,
  `ops_event`, `test_result`, `routing_lesson`, `security_lesson`, and
  `reference_pattern`.
- [x] Add memory source ids/citations to recall outputs used by admin traces
  and worker preflight.
- [x] Add export/delete/redaction gates for durable memory records.
- [x] Keep mastery recommendations out of automatic hot-path routing until
  eval and rollback gates exist.
- [x] Verify secret-like strings are rejected or redacted before promotion.

## Phase 4 - Agent And Tool Governance

**References:** OpenAI Agents SDK, Google ADK, Microsoft Agent Governance
Toolkit, gstack, OpenAI Symphony, agent-skills, mattpocock skills.

**Files:**
- Modify: `agent_tasks*`
- Modify: `agent_runtime/*`
- Modify: `tool_gateway/*`
- Modify: `routes/agent*.py`
- Modify: `deepcode-cli` worker/task files after submodule plan approval
- Test: `tests/test_agent*.py`
- Test: `tests/test_tool_gateway*.py`
- Test: `tests/test_worker_summary_constraints.py`

- [x] Add risk class, allowed actions, approval requirement, evidence refs,
  and rollback owner to agent task/tool metadata.
- [x] Fail closed when dangerous tool classes lack explicit approval metadata.
- [x] Record tool/MCP provenance in audit events.
- [x] Require LiMa worker summaries to report changed files, tests,
  remaining risks, and review status.
- [x] Keep deploy, push, GitHub write, cloud, database migration, and hardware
  actions behind explicit gate metadata.

## Phase 5 - MCP Access Plane

**References:** Official MCP Registry, modelcontextprotocol servers, Google
MCP, awesome-mcp-servers, Agent-Reach, cc-connect, bluebox, RuVector MCP.

**Files:**
- Modify: `docs/reference/MCP_CONNECTOR_CATALOG.md`
- Create: `lima_mcp/access_plane.py`
- Test: `tests/test_mcp_access_plane.py`

- [x] Keep LiMa dev-search MCP tools active and read-only by default.
- [x] Promote only foundation candidates first: filesystem read, git read,
  docs lookup, time, and memory/query surfaces.
- [x] Require owner, allowlist, credential boundary, timeout, audit event, and
  failure mode before enabling any connector.
- [x] Keep business, billing, messaging, cloud-control, scraping, media, voice,
  and database-write connectors off by default.

## Phase 6 - Eval, Observability, And Cost

**References:** promptfoo, DeepEval, Ragas, LangFuse, OpenTelemetry,
Prometheus, Portkey, LiteLLM.

**Files:**
- Create: `eval_registry.py`
- Modify: `routing_engine.py`
- Modify: `health_tracker*`
- Modify: `probe_loop.py`
- Modify: worker telemetry files
- Test: `tests/test_eval_registry.py`

- [x] Add a unified eval registry linking model, route, fixture, score,
  promotion decision, and evidence.
- [x] Define route-level cost, latency, cache, cooldown, and failure-state
  metric names before adding exporters.
- [x] Add per-task budget envelopes for LiMa worker runs.
- [x] Keep hosted tracing/eval services disabled until data residency,
  redaction, self-hosting, and license gates pass.

## Phase 7 - LiMa UX And Workflow

**References:** OpenCode, Warp, Aider, gstack, Open Design, ClaudePrism,
vibe-coding-cn, agent-skills.

**Files:**
- Modify: `deepcode-cli` submodule after explicit submodule plan
- Modify: `docs/LIMA_MANAGEMENT.md`
- Test: LiMa npm tests and Server/Worker contract tests

- [x] Add opt-in stage commands for plan, review, test, and ship workflows.
- [ ] Add review-context prefetch that explains why each file was selected.
- [ ] Keep logs plain-text compatible and audit-safe.
- [ ] Keep external CLI discovery allowlisted and opt-in.
- [ ] Prevent skill packs from changing tool permissions, provider routing, or
  deployment behavior.

## Phase 8 - ESP32 And Hardware Companion Expansion

**References:** ElatoAI, RuView, PersonaPlex, pocket-tts, VoxCPM, Qwen3-TTS,
GLM-OCR, GR00T, nano-world-model, OpenClaw-RL.

**Files:**
- Modify: `device_gateway/*`
- Create: `device_gateway/protocol_families.py`
- Modify: `routes/device_gateway.py`
- Modify: `esp32S_XYZ` after submodule plan approval
- Test: fake-device and real-device gated smokes
- Test: `tests/test_device_gateway_protocol_families.py`
- Docs: `docs/ESP32S_XYZ_MANAGEMENT.md`
- Docs: `docs/reference/HARDWARE_COMPANION_REFERENCES.md`

- [x] Finish writing-machine fake U8 and real U8/U1 safety evidence before
  adding new protocol families.
- [x] Add separate schemas only after approval: `display_task`,
  `audio_stream`, `speech`, `ocr_result`, and `vision_observation`.
- [x] Keep motion, voice, display, OCR, camera, and perception on separate
  allowlists.
- [x] Keep voice cloning, vital-sign sensing, fall/distress detection,
  through-wall sensing, and persona training disabled until consent, privacy,
  model-license, retention, false-positive, and hardware-validation gates pass.

## Verification Cadence

Each implementation slice must record:

- exact files changed;
- focused test command and result;
- broader regression command when the touched surface is shared;
- doc files updated;
- deployment or rollback evidence when VPS behavior changes;
- commit hash after merge/push.

Default verification commands for reference-capability work:

```powershell
python -m py_compile <touched python files>
python -m pytest <focused tests> -q --ignore=active_model
git diff --check -- <touched files>
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" <touched docs/code>
```
