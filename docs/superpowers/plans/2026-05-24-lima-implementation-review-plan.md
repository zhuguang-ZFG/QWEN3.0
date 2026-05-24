# LiMa Implementation And Review Plan

> Date: 2026-05-24
> Mode: user implements code, Codex performs code review and verification.
> Source inputs:
> - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`
> - `docs/reference/LIMA_10_SUBSYSTEM_OPEN_SOURCE_RECOMMENDATIONS.md`
> - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`

## Goal

Turn the recent reference learning into small LiMa-native implementation
slices. The user writes the code. Codex reviews each slice for correctness,
security, regression risk, tests, and whether it stays inside LiMa's existing
architecture.

This plan is intentionally not a dependency adoption plan. It uses outside
projects as design references while keeping LiMa's own router, key custody,
worker gates, memory records, Device Gateway, and audit model authoritative.

## Collaboration Contract

User responsibilities:

- Implement one slice at a time.
- Keep each slice small enough to review in one pass.
- Include tests, docs, and migration notes with the code.
- Do not introduce external dependencies unless that slice explicitly allows a
  gated dependency review.
- Provide the review command output or let Codex run it locally after coding.

Codex responsibilities:

- Review in code-review mode: bugs, regressions, missing tests, security risks,
  data leaks, bad abstractions, and incomplete gates first.
- Verify that each slice honors the plan, the existing codebase patterns, and
  the no-permission-expansion rule.
- Run focused tests and report exact failures.
- Refuse silent broadening of cloud, browser, database, messaging, deployment,
  hardware, or hosted observability permissions.
- Push only after the slice is reviewed, fixed, tested, and approved.

Review package expected from the user for each slice:

- Files changed.
- What behavior changed.
- Tests added or updated.
- Commands run and results.
- Any new dependency, network call, credential, file path, database, or external
  service touched.
- Rollback note.

## Global Implementation Rules

- No mass framework rewrite.
- No dependency dump.
- No AGPL/GPL/LGPL/mixed-license/source-available/archived/unresolved project
  as a runtime dependency without a separate isolation decision.
- No private prompt, dataset, schema, code, trace, key, or hardware telemetry
  leaves LiMa without explicit consent and redaction.
- New provider, MCP, browser, database, cloud, deployment, messaging, or
  hardware authority must start `default_off`.
- Every new abstraction needs tests and one concrete caller.
- Every new metric/audit field must avoid raw prompt, key, cookie, file body,
  dataset row, and personal data labels.

## Milestone 0 - Baseline And Review Harness

Purpose:

- Make future reviews predictable before implementation accelerates.

Implementation tasks:

- Add or update a developer checklist under `docs/` that points to the test
  commands for router, context, memory, eval, agent task, and streaming areas.
- Add a lightweight "review packet" template for future slices.
- Record current known unrelated untracked files as out of scope for this
  plan; do not stage them.

Likely files:

- `docs/`
- `progress.md`

Tests and verification:

- `git status --short --branch`
- `git diff --check`
- Existing focused tests touched by the checklist only if files change.

Codex review focus:

- Does the checklist match real commands?
- Does it avoid creating fake completion claims?
- Does it make review packets easy to audit?

Exit criteria:

- A human can open one doc and know how to submit a slice for review.

## Milestone 1 - Router, Backend Registry, Key Pool, And Cost Telemetry

References:

- LiteLLM and Portkey for provider abstraction, fallback, cost/rate-limit, and
  gateway vocabulary.
- Ollama and vLLM for local/self-hosted model boundaries.
- Existing LiMa files already include `backends.py`, `http_caller.py`,
  `key_pool.py`, `budget_manager.py`, `backend_reputation.py`,
  `capability_matrix.py`, and router tests.

Implementation slices:

1. Backend capability normalization:
   - Ensure all routing components read capability and GFW/proxy facts from
     `backends.py`.
   - Remove or mark duplicated local capability tables outside the registry.
   - Keep provider keys in `key_pool.py`, not in router logic.

2. Key-pool runtime evidence:
   - Add structured non-secret key selection events:
     `provider`, `backend`, `key_slot_hash`, `reason`, `cooldown`, `attempt`.
   - Never log raw keys or full provider secrets.
   - Add tests for multi-key provider rotation, exhaustion, and cooldown.

3. Fallback and rate-limit classification:
   - Normalize auth, quota, rate-limit, timeout, network, malformed response,
     and quality failure categories.
   - Feed those categories into `backend_reputation.py` and
     `budget_manager.py`.

4. Cost and quota telemetry shape:
   - Add an internal data structure for estimated prompt tokens, completion
     tokens, backend cost class, and remaining quota score.
   - Keep it best-effort; do not block free/local backends because token
     counts are unavailable.

Likely files:

- `backends.py`
- `http_caller.py`
- `key_pool.py`
- `budget_manager.py`
- `backend_reputation.py`
- `capability_matrix.py`
- `smart_router.py`
- `tests/test_backend_registry.py`
- `tests/test_http_caller.py`

Tests and verification:

- `python -m pytest tests/test_backend_registry.py tests/test_http_caller.py`
- Add new unit tests for key-pool selection and fallback classification.
- `python -m pytest tests/test_complexity.py` if routing complexity changes.

Codex review focus:

- No duplicated backend source of truth.
- No secret logging.
- Correct behavior under concurrent requests.
- Clear fallback behavior when all keys/providers fail.
- No LiteLLM/Portkey dependency introduced by accident.

Exit criteria:

- Router behavior is still compatible with current API responses.
- Multi-key provider behavior is test-covered.
- Failure categories are auditable and do not leak secrets.

## Milestone 2 - Async And Concurrency Safety

References:

- `aiohttp` for async HTTP design.
- Existing `context_pipeline/ensemble.py` and LiMa's concurrent routing needs.

Implementation slices:

1. Async boundary design:
   - Define whether async calls live beside or inside `http_caller.py`.
   - Keep sync API compatibility for existing callers.
   - Add cancellation and timeout semantics before adding new clients.
   - Status 2026-05-24: M2-S1 keeps async calls beside sync calls in
     `http_caller.py`, preserves sync public signatures, and adds `httpx`
     sync/async clients.

2. Concurrent request tests:
   - Add tests for multiple simultaneous provider calls with independent
     key-pool decisions.
   - Add timeout and cancellation tests.
   - Status 2026-05-24: M2-S2/S3 adds async stream timeout tests and
     speculative async winner/cancellation tests. Provider-key stress tests can
     be expanded later if key-pool contention becomes observable.

3. Backpressure and resource limits:
   - Add per-provider max concurrency fields if needed.
   - Ensure local models and weak/free backends cannot stampede.
   - Status 2026-05-24: no new runtime limit fields were added. M2 keeps
     resource behavior compatible and defers provider-level backpressure until
     real concurrency evidence justifies it.

Likely files:

- `http_caller.py`
- `key_pool.py`
- `context_pipeline/ensemble.py`
- `tests/test_http_caller.py`
- `tests/test_complexity.py`

Tests and verification:

- Focused async unit tests.
- Existing router tests.

Codex review focus:

- No event-loop misuse.
- No shared mutable key state races.
- Timeouts and cancellation are deterministic.
- Sync compatibility remains intact.

Exit criteria:

- LiMa can process multiple requests concurrently without shared key/provider
  corruption.

Current M2-S1 review notes:

- `httpx` 0.28.1 is available in the local environment and supports the
  `proxy=` client argument used for GFW backends.
- Review fixed key-pool failure reporting so internal `BackendError` status
  codes are preserved instead of converted to 429.
- Focused verification after review: `test_http_caller.py` plus
  `test_routing_engine.py` returned 97 passed.

Current M2 closure notes:

- `streaming.py` now provides `bridge_stream_async()` and
  `speculative_stream()` can use async-native stream/API callables.
- `routes/v3_adapters.py` and `routes/stream_handlers.py` expose async-native
  stream adapters while keeping legacy sync bridge functions.
- `speculative.py` now provides `speculative_call_async()` and a sync
  compatibility facade.
- Review fixed two behavioral regressions:
  - first-chunk timeout is enforced before waiting indefinitely for a chunk;
  - invalid fast speculative responses no longer cancel valid slower responses.
- Focused verification after M2 review: `test_streaming.py`,
  `test_routing_engine.py`, and `test_http_caller.py` returned 108 passed.

## Milestone 3 - Context Graph, AST, Reranking, And Retrieval Evaluation

References:

- LightRAG, GraphRAG, OpenRAG, Sirchmunk, rerankers, tree-sitter, FastEmbed,
  LlamaIndex, claude-context, Understand-Anything.

Implementation slices:

1. Graph index interface:
   - Add a LiMa-owned `code_context.graph_index` interface if not already
     present.
   - Provide in-memory implementation first.
   - Do not bind to GraphRAG/LightRAG runtime yet.

2. AST extraction prototype:
   - Add feature-flagged AST extraction for Python files.
   - Start with standard-library `ast` for Python before optional tree-sitter.
   - Define a future tree-sitter adapter boundary without adding it yet.

3. Reranker interface:
   - Define a `context_pipeline.reranking` abstraction that accepts candidate
     chunks and returns scored chunks with reasons.
   - Add a deterministic lexical/test reranker first.
   - Keep hosted rerankers default-off.

4. Retrieval fixture and metrics:
   - Add a small fixture repo/docs corpus.
   - Add expected relevant files/chunks.
   - Track recall, precision-like hit rate, and source evidence.

Likely files:

- `code_context/`
- `context_pipeline/`
- `tests/test_code_context_index.py`
- `tests/test_context_pipeline.py`
- New fixture files under `tests/fixtures/`

Tests and verification:

- `python -m pytest tests/test_code_context_index.py`
- `python -m pytest tests/test_context_pipeline.py`
- Add reranking and graph-index tests.

Codex review focus:

- No private path scanning without allowlists.
- Deterministic tests without network.
- Reranking explains why candidates were chosen.
- AST parser failure falls back safely.

Exit criteria:

- Graph/index/rerank interfaces exist and are tested without external runtime
  dependencies.

Closure notes:

- Completed on 2026-05-24 with no new runtime dependency.
- Added `code_context.graph_index.GraphIndex` and the default
  `InMemoryGraphIndex`.
- Added `code_context.ast_adapter.AstExtractor` and Python stdlib AST
  extraction while keeping tree-sitter as a future gated adapter.
- Added `context_pipeline.retrieval_eval` metrics for recall, precision@k, hit
  rate, MRR, per-query evaluation, and summary output.
- Added fixture-backed tests for graph traversal, AST extraction, reranking,
  and retrieval metrics.
- Codex review fixed two edge cases:
  - import relations now resolve full, root, and leaf module names from
    `module_map`;
  - missing retrieval result rows count as misses instead of being skipped.

## Milestone 4 - Memory Taxonomy, Promotion, Deletion, And Redaction

References:

- Mem0, Letta, Zep, Memobase, stash, hindsight, RuVector.

Implementation slices:

1. Memory record taxonomy:
   - Map LiMa memory into `episode`, `fact`, `preference`,
     `working_context`, `promotion`, `rejection`, `evidence`, and `profile`
     categories.

2. Promotion rules:
   - Add explicit promotion evidence and rejection reason fields.
   - Do not auto-promote raw observations.

3. Secret and PII redaction:
   - Add tests proving keys, cookies, tokens, URLs with secrets, and private
     paths are not promoted.

4. Delete/export controls:
   - Add API or internal function boundaries for memory export and deletion
     before adding richer user/profile memory.

Likely files:

- `session_memory/`
- `context_pipeline/hierarchical_memory.py`
- `tests/test_compactor.py`
- `tests/test_advanced_patterns.py`

Tests and verification:

- `python -m pytest tests/test_compactor.py tests/test_advanced_patterns.py`
- New memory taxonomy/redaction tests.

Codex review focus:

- No autonomous self-editing memory without audit.
- Deletion/export semantics are real, not comments.
- Secrets are redacted before persistence.

Exit criteria:

- Memory is typed, auditable, redactable, and reversible enough for later
  vector/graph experiments.

Closure notes:

- Completed on 2026-05-24 with no new runtime dependency.
- Added `MemoryEntry.memory_type` and fixed memory SELECT paths to preserve
  typed memory results.
- Added reusable `session_memory.redact` helpers for request-time and daemon
  memory writes.
- Added promotion, JSONL audit, deletion, and JSON export helpers.
- Codex review fixed two security-test gaps:
  - sanitizer rejection no longer falls back to raw memory storage;
  - promotion evidence is redacted before detail and audit persistence.

## Milestone 5 - Evaluation, Quality Gate, And Structured Output

References:

- Promptfoo, DeepEval, Ragas, Instructor, Guardrails AI.

Implementation slices:

1. Eval fixture format:
   - Define a YAML or JSON fixture format for prompt, expected behavior,
     allowed backends, tags, and assertions.
   - Keep it compatible in spirit with promptfoo/deepeval but LiMa-owned.

2. Coding eval extension:
   - Extend `coding_eval.py` with structured assertions:
     exact output, contains/does-not-contain, JSON schema, tool-call shape,
     citation/evidence presence, and refusal correctness.

3. Quality gate schema:
   - Replace ad-hoc dicts with typed result shape for pass/fail, score,
     reasons, repairable, and severity.

4. RAG eval lane:
   - Add context precision/recall-like metrics once Milestone 3 fixtures exist.

Likely files:

- `coding_eval.py`
- `quality_gate.py` or `routes/quality_gate.py`
- `tests/test_coding_eval.py`
- `tests/test_quality_gate.py` if present or new

Tests and verification:

- `python -m pytest tests/test_coding_eval.py`
- Focused quality gate tests.

Codex review focus:

- No hosted eval service by default.
- Failures are explainable.
- Structured output validation does not mask malformed model output.

Exit criteria:

- Evaluations can catch regressions in routing, coding, exact-output, and RAG
  retrieval without network access.

Closure notes:

- Completed on 2026-05-24 with no hosted eval service and no new dependency.
- Added structured `QualityGateResult` plus `quality_check_typed()` while
  preserving the legacy boolean `quality_check()` API.
- Added local coding eval fixtures for exact output, Python code, JSON output,
  safety refusal, and router explanation.
- Codex review fixed:
  - mojibake in quality-gate source/tests by using ASCII source with Unicode
    escapes;
  - missing `repairable=True` for short repairable answers;
  - safety refusal handling for clearly harmful prompts;
  - `CodingCase.max_chars` and JSON-list fixture loading.

## Milestone 6 - Observability And Metrics

References:

- OpenTelemetry Python, Prometheus Python client, LangFuse, Phoenix, MLflow.

Implementation slices:

1. Metric naming spec:
   - Define metric names for request count, latency, backend failure category,
     key-pool selection, cooldown, quality score, eval pass rate, and worker
     task status.

2. Internal event model:
   - Add a small internal event structure before exporters.
   - Avoid raw prompts, keys, cookies, file contents, dataset rows, and user
     personal data.

3. Optional Prometheus exporter:
   - Add only after metric names and redaction tests are accepted.
   - Default off.

4. Trace correlation:
   - Add request/task correlation IDs that work across router, worker, eval,
     and streaming logs.

Likely files:

- `health_tracker.py`
- `probe_loop.py`
- `backend_reputation.py`
- `routes/agent_tasks.py`
- New `observability/` module if needed

Tests and verification:

- Unit tests for metrics serialization and redaction.
- Existing health/router tests.

Codex review focus:

- No high-cardinality labels containing prompts or paths.
- Exporters default off.
- Correlation IDs do not become user tracking identifiers.

Exit criteria:

- LiMa has stable internal telemetry names and redaction rules before adding
  hosted observability.

Current M6 closure notes:

- M6-S1/S2/S4 completed on 2026-05-24 with no new runtime dependency.
- Added `observability.events.LiMaEvent` plus factory helpers.
- Added `observability.metrics` in-memory aggregation and snapshot helpers.
- Added `docs/OBSERVABILITY_EVENTS.md`.
- Codex review fixed event-object redaction so metadata and key-pool details
  cannot keep raw prompt/key/cookie-like values.
- M6-S3 remains pending: wire `http_caller.py`, `routing_engine.py`,
  `routes/quality_gate.py`, `key_pool.py`, and `budget_manager.py`.

## Milestone 7 - Worker Governance, Tool Gateway, MCP, And A2A

References:

- OpenAI Agents SDK, Google ADK, Agent Governance Toolkit, MCP Python SDK, A2A,
  gstack, Symphony, AgentConductor, Solvita, RecursiveMAS, Qoder.

Implementation slices:

1. Agent task risk metadata:
   - Add fields such as `risk_class`, `allowed_tools`, `requires_approval`,
     `evidence_refs`, `rollback_owner`, `network_policy`, and `data_policy`.
   - Use AgentConductor as a design pressure: start with the smallest useful
     workflow and expand agent roles only when task difficulty, risk, or eval
     evidence justifies the extra coordination/token cost.

2. Tool gateway permission model:
   - Define tool authority classes:
     `read_only`, `write_workspace`, `network_read`, `network_write`,
     `database_read`, `database_write`, `browser`, `deployment`, `hardware`.
   - Default to no authority unless a task grants it.
   - Use RecursiveMAS as a communication-efficiency reminder: prefer compact
     typed envelopes, artifact ids, and evidence refs over verbose
     agent-to-agent prose.

3. MCP compatibility plan:
   - Add read-only MCP-style tool metadata compatibility first.
   - Do not turn on third-party MCP servers by default.

4. A2A contract research:
   - Map current LiMa Server to LiMa Code task contract to A2A-like fields.
   - No protocol replacement until schema parity exists.
   - Use Solvita-style roles only as opt-in task modes: planner, solver,
     oracle/reviewer, and hacker/adversarial tester. Store lessons as
     evidence-weighted mastery events, not raw self-editing memory.

5. Real software engineering workflow:
   - Use Qoder-style product lessons for repository understanding,
     decomposition, verification, and long-horizon coding work.
   - Keep closed product/model claims as references only until LiMa-owned
     benchmarks prove value.

Likely files:

- `routes/agent_tasks.py`
- `tool_gateway` or related worker files
- `deepcode-cli/` docs or contracts if needed
- `tests/test_agent_task_routes.py`
- `tests/test_admin_agent_audit.py`

Tests and verification:

- `python -m pytest tests/test_agent_task_routes.py tests/test_admin_agent_audit.py`
- Permission model tests.

Codex review focus:

- No tool receives hidden authority.
- Approval-required tasks cannot execute mutating tools before approval.
- Audit output is complete enough for postmortem.

Exit criteria:

- Worker/tool permissions are explicit, test-covered, and reviewable before
  sandbox/cloud/MCP expansion.

## Milestone 8 - Sandbox Evaluation Without Production Adoption

References:

- E2B, CubeSandbox, Symphony.

Implementation slices:

1. Sandbox provider interface:
   - Define methods for create, upload fixture, run command, collect logs,
     collect diff, terminate.
   - Provide a fake provider first.

2. Disposable fixture:
   - Create a no-secret fixture repo and command.
   - Verify cleanup and timeout behavior.

3. Provider comparison note:
   - Compare E2B and CubeSandbox on license, hosting, network egress,
     filesystem persistence, cost, isolation, and cleanup.

Likely files:

- New `sandbox/` or worker module.
- `tests/test_sandbox_provider.py`
- Docs under `docs/reference/`

Tests and verification:

- Fake-provider unit tests only.
- No live cloud sandbox in default CI.

Codex review focus:

- No real secrets enter sandbox tests.
- No production worker uses the sandbox provider until explicitly wired.
- Cleanup/timeout is not optional.

Exit criteria:

- LiMa can evaluate sandbox providers safely without adopting one.

## Milestone 9 - Streaming And Frontend/API Progress Events

References:

- `sse-starlette`, VidBee SSE task events, Nunchi HTTP/SSE observability.

Implementation slices:

1. Streaming contract:
   - Document event names for token, tool_start, tool_delta, tool_end,
     warning, error, done, and audit_ref.

2. SSE compatibility:
   - If using FastAPI, evaluate `sse-starlette` behind a feature flag.
   - Otherwise improve current `streaming.py` with backpressure/disconnect
     tests.

3. Task progress stream:
   - Add agent task progress events after permission and audit fields exist.

Likely files:

- `streaming.py`
- `server.py` or route modules
- `routes/agent_tasks.py`
- Streaming tests if present or new

Tests and verification:

- Unit tests for disconnect, timeout, error, done.
- API smoke for streaming endpoint if local server is used.

Codex review focus:

- Streaming errors terminate cleanly.
- No event leaks hidden chain-of-thought, keys, cookies, or private file bodies.
- Clients can recover from disconnects.

Exit criteria:

- Streaming is observable, bounded, and compatible with future UI/task progress.

## Milestone 10 - Data Workbench And Research Artifacts

References:

- Quelmap, OpenRAG, Youdao Baoku, GLM-OCR, Algebrica, Flipbook, OpenMontage.

Implementation slices:

1. Dataset ingestion policy:
   - Define accepted file types, max size, retention, schema redaction, and
     local-only default.

2. Python sandbox boundary:
   - Define what generated analysis code may import, read, write, and execute.
   - Use fake sandbox until worker governance is ready.

3. Research artifact schema:
   - Store source URL, retrieval date, summary, evidence refs, generated
     artifact path, and privacy class.

Likely files:

- New docs first.
- Later `data_workbench/` or `research/` modules.

Tests and verification:

- Policy tests once code exists.
- No cloud provider use in default tests.

Codex review focus:

- Dataset schema and rows do not leave local machine without consent.
- Generated Python is sandboxed and auditable.
- Artifacts cite sources and retention.

Exit criteria:

- LiMa can safely plan data/research workflows before executing them.

## Milestone 11 - DevOps, Deployment, And Terminal UX

References:

- Caddy, Piku, Nixpacks, Dagger, Rich, Textual, OpenCode, Aider.

Implementation slices:

1. Deployment inventory:
   - Document current VPS deployment, systemd services, ports, reverse proxy,
     env files, rollback, and smoke commands.

2. Caddy/Nixpacks/Piku evaluation:
   - Compare with current deployment.
   - No replacement until current flow has rollback tests.

3. Rich CLI rendering:
   - Improve local CLI status output only where plain logs remain parseable.
   - Do not require a TUI for automation.

4. Aider-style editing protocol:
   - Borrow SEARCH/REPLACE and repo-map ideas for LiMa Code review prompts,
     not as a runtime dependency.

Likely files:

- `docs/`
- `deepcode-cli/`
- CLI output modules if present

Tests and verification:

- Snapshot or golden text tests for CLI output.
- Deployment docs smoke commands.

Codex review focus:

- No accidental auto-deploy.
- Terminal UX does not hide errors.
- Generated logs remain machine-readable enough for review.

Exit criteria:

- VPS and CLI work become easier to operate without reducing auditability.

## Milestone 12 - Hardware Companion Later Lane

References:

- esp32S_XYZ, ElatoAI, RuView, VoxCPM, Qwen3-TTS, pocket-tts, PersonaPlex,
  GR00T, nano-world-model.

Implementation slices:

1. Finish writing-machine direct control first:
   - U8 connects to LiMa Device Gateway.
   - Bounded `motion_task` commands.
   - `motion_event` telemetry.
   - Fake-device and real-device smoke.

2. Voice/display/perception are separate protocol families:
   - `audio_stream`, `speech`, `display_task`, `ui_state`, `ocr_result`,
     `vision_observation`, and future ambient perception.

3. Consent and safety:
   - Voice cloning, camera/OCR, WiFi CSI people sensing, fall/distress, and
     through-wall detection are all default-off.

Likely files:

- Device Gateway modules.
- `docs/ESP32S_XYZ_*`
- `docs/reference/HARDWARE_COMPANION_REFERENCES.md`

Tests and verification:

- Fake-device tests before real-device tests.
- Real-device smoke only with explicit operator approval.

Codex review focus:

- No smart-hardware action can bypass allowlists.
- No perception signal directly triggers motion/hardware without human-gated
  policy.
- Hardware logs distinguish simulated and real evidence.

Exit criteria:

- Writing-machine control is stable before companion hardware expands.

## Recommended Order

1. Milestone 0: review harness.
2. Milestone 1: backend registry/key-pool/telemetry.
3. Milestone 5: eval fixture and quality gate shape.
4. Milestone 3: graph/rerank interfaces.
5. Milestone 4: memory taxonomy/redaction.
6. Milestone 7: worker governance/tool permissions.
7. Milestone 6: observability metrics.
8. Milestone 2: async/concurrency upgrade.
9. Milestone 8: sandbox fake provider and comparison.
10. Milestone 9: streaming/task progress.
11. Milestone 11: deployment and CLI UX.
12. Milestone 10: data workbench.
13. Milestone 12: hardware companion later lane.

The first three milestones give the strongest safety net: router correctness,
tests/evals, and review discipline. After that, larger capabilities can be
added without guessing.

## Review Checklist For Codex

For every user-coded slice, Codex should check:

- Correctness:
  - Does the implementation satisfy the exact milestone slice?
  - Are edge cases and failure modes covered?
  - Are old APIs still compatible?
- Security:
  - Are secrets, cookies, prompts, file contents, dataset rows, and private
    paths redacted from logs/metrics/traces?
  - Did any tool/provider/connector gain authority by default?
  - Is external network access explicit and gated?
- Tests:
  - Are unit tests focused and deterministic?
  - Are integration tests gated if they need network, hardware, VPS, or cloud?
  - Do existing related tests still pass?
- Architecture:
  - Does the change reuse existing LiMa modules and naming?
  - Is the abstraction justified by a real caller?
  - Is there a rollback path?
- Documentation:
  - Is the new behavior documented where operators will find it?
  - Are limitations and non-goals explicit?
- Release readiness:
  - Is there a smoke command?
  - Is there a migration note if state/schema changed?
  - Is deployment/push/hardware action still approval-gated?

## Review Response Format

Codex should respond with:

1. Findings first, ordered by severity, with file and line references.
2. Open questions or assumptions.
3. Tests run and results.
4. Approval status:
   - `approved`;
   - `approved after minor fixes`;
   - `changes requested`;
   - `blocked`.
5. Exact next action.

## Done Definition

The plan is considered implemented only when:

- Each completed milestone has code, tests, docs, and review notes.
- P0 gates are enforced in code, not only documented.
- No new dependency has unresolved license/security/data-flow review.
- No external service receives private data by default.
- No worker, MCP connector, browser, deployment path, or hardware path mutates
  anything without explicit task authorization.
- The main branch and GitHub remote contain the reviewed commits.
