# LiMa Agent Autonomy Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for implementation phases, `superpowers:verification-before-completion` before marking a phase done, and `safety-guard` for any autonomous runner, VPS operation, shell execution, GitHub write, or tool-execution change.
>
> **Current policy:** This is a plan document only. Do not change runtime code until the owner starts a specific implementation phase.

**Goal:** Turn LiMa from a private coding-router backend into a small, auditable, test-backed agent workbench that can plan, code, review, test, remember, and improve its own workflows under human-controlled boundaries.

**Non-goal:** Do not build a "fully autonomous production mutator" in one jump. LiMa should first become a gated autonomous development assistant: it can propose changes, run tests, collect evidence, and prepare patches, but production deploys, destructive commands, credential changes, and broad repository rewrites remain approval-gated.

**Baseline on 2026-05-23:**

- LiMa is a private personal coding assistant backend, not a public SaaS agent platform.
- Main request path works through OpenAI/Anthropic-compatible endpoints, route selection, backend calls, quality checks, stats, and Session Memory writes.
- Session Memory writes and compaction triggers exist, but always-on typed memory and prompt-time recall are not first-class in `server.py`.
- Graph retrieval and reranking exist, but `_reranked` results are not yet injected into prompt context.
- Tool Gateway is hardened with `shell=False`, argument validation, copied HTTP args, and audit events.
- `ConcurrencyPool` exists and is tested, but has not replaced provider key scheduling.
- Latest known LiMa target suite: `382 passed, 8 skipped`. Do not call this unrestricted full-repo pytest.

---

## Reference Ranking

| Project | Value For LiMa | Borrow | Do Not Copy |
|---|---:|---|---|
| `google/adk-python` | 9/10 | Workflow runtime, graph execution, fan-out/fan-in, retry, state, task delegation, human-in-the-loop. | Do not make ADK a hard dependency in the production router yet. |
| `openai/openai-agents-python` | 8.5/10 | Agent roles, handoffs, guardrails, sessions, tracing, sandbox-agent concepts. | Do not replace LiMa's routing layer with the SDK wholesale. |
| `lsdefine/GenericAgent` | 8/10 | Minimal loop, layered memory, skill crystallization after task success. | Do not grant arbitrary desktop/system control or dynamic package install by default. |
| `EvoMap/evolver` | 7.5/10 | Genes/Capsules/Events as compact, auditable evolution assets; validation before promotion. | Do not join external worker networks or ingest remote genes without local validation. |
| `msitarzewski/agency-agents` | 6/10 | Role library, domain-specific agent specs, success metrics. | Do not create dozens of persona agents before LiMa has orchestration and trace gates. |

External references reviewed:

- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- Google ADK: https://github.com/google/adk-python
- GenericAgent: https://github.com/lsdefine/GenericAgent
- EvoMap Evolver: https://github.com/EvoMap/evolver
- Agency Agents: https://github.com/msitarzewski/agency-agents
- Existing LiMa reference evaluation: `docs/REFERENCE_PROJECT_EVALUATION.md`

---

## Target Shape

LiMa should grow into this local-first architecture:

```text
IDE / terminal agent / owner
    |
    v
LiMa API compatibility layer
    |
    +-- evidence context
    |     +-- graph retrieval injection
    |     +-- typed memory recall
    |     +-- retrieval trace
    |
    +-- agent workbench
    |     +-- planner
    |     +-- coder
    |     +-- reviewer
    |     +-- tester
    |     +-- memory/evolution agent
    |
    +-- autonomy ledger
    |     +-- tasks
    |     +-- runs
    |     +-- tool calls
    |     +-- patches
    |     +-- tests
    |     +-- approvals
    |
    +-- skill/gene store
          +-- reusable skills
          +-- compact genes
          +-- validation commands
          +-- promotion history
```

The first useful agent team is five agents, not dozens:

| Agent | Job | Must Produce |
|---|---|---|
| Planner | Break request into files, tests, risks, and phases. | Structured plan JSON plus Markdown summary. |
| Coder | Implement one approved phase. | Patch summary, touched files, known risks. |
| Reviewer | Find bugs, security risks, and missing tests. | Severity-ranked findings with file/line evidence. |
| Tester | Run agreed checks and summarize failures. | Command, exit code, key output, retry advice. |
| Memory/Evolution | Extract reusable lessons only after success. | Candidate skill/gene with validation evidence. |

---

## Safety Model

Autonomy levels:

| Level | Name | Allowed |
|---|---|---|
| L0 | Read-only advisor | Read code/docs, write analysis docs only. |
| L1 | Local patch proposer | Create patches in workspace, no deploy, no push. |
| L2 | Local verifier | Run local tests, compile, secret scans, produce evidence. |
| L3 | Branch worker | Create branch/commit after explicit approval, no production deploy. |
| L4 | VPS operator | Deploy only with explicit owner approval and rollback record. |
| L5 | Fully autonomous production | Not allowed for now. Requires mature ledger, approvals, rollback, and monitoring. |

Default for LiMa autonomous work should be L1-L2. L3 and L4 need explicit owner approval. L5 is a future research target, not an implementation target.

Hard approval gates:

- Any `git push`, GitHub PR creation, or repository write outside the current workspace.
- Any VPS command, deployment, service restart, firewall/nginx edit, or credential change.
- Any destructive command: delete, reset, checkout discard, database migration/drop, package publish.
- Any broad shell executor change.
- Any change that sends private code, logs, paths, tokens, or memory contents to external search or external worker networks.

---

## Phase 0: Reference Intake And Boundaries

**Purpose:** Preserve what is worth borrowing before coding.

**Files:**

- Create: `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`
- Update: `docs/DOCUMENTATION_STATUS.md`
- Update: `findings.md`
- Update: `progress.md`

**Steps:**

- [ ] Record the five reference projects and exact borrowed concepts.
- [ ] Record rejected concepts: unbounded shell, external worker pools, many persona agents without orchestration, direct production mutation.
- [ ] Check licenses before copying any code. Prefer concept borrowing, not vendoring.
- [ ] Verify no secrets in the new docs:

```powershell
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT\docs\reference D:\GIT\docs\superpowers\plans\2026-05-23-agent-autonomy-evolution.md
```

**Exit criteria:**

- Reference notes exist.
- Documentation status points to this plan.
- No credential-like strings appear in the new docs.

---

## Phase 1: Retrieval And Memory Evidence Before Agents

**Purpose:** Agents need grounded context before they can usefully modify code.

**Files to inspect first:**

- `routing_engine.py`
- `server.py`
- `context_pipeline/reranking.py`
- `context_pipeline/graph_retrieval.py`
- `session_memory/store.py`
- `session_memory/processor.py`
- `docs/REFERENCE_PROJECT_EVALUATION.md`

**Implementation shape:**

- Add or reuse a retrieval injector that converts reranked code graph results into a compact prompt block.
- Add trace data showing selected files/entities/scores and token cost.
- Add typed memory recall for small, cited memories only.
- Keep memory consolidation async; never do expensive consolidation inside `/v1/chat/completions`.

**Tests:**

- Retrieval formatting includes source file, symbol/entity, reason, and score.
- Prompt injection is bounded by token/character budget.
- Sensitive files such as `.env`, ignored credential files, and local temp probes are never injected.
- Existing routing tests still pass.

**Suggested commands:**

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_context.py test_routing_engine.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest tests -q --ignore=active_model
```

**Exit criteria:**

- Coding requests can receive traceable repo context.
- Admin or debug trace can explain why context was selected.
- No production deploy yet unless explicitly requested.

---

## Phase 2: Agent Workbench Data Model

**Purpose:** Build the audit trail before running autonomous loops.

**Create module:**

```text
agent_workbench/
  __init__.py
  models.py
  store.py
  roles.py
  trace.py
```

**Minimum data structures:**

- `AgentTask`: id, title, goal, autonomy_level, status, created_at.
- `AgentRun`: id, task_id, role, model/backend, input_ref, output_ref, status, started_at, ended_at.
- `ToolCallRecord`: run_id, tool_name, arguments_hash, allowed, result_summary, error_class.
- `PatchRecord`: task_id, touched_files, diff_hash, tests_required, approval_state.
- `ApprovalRecord`: task_id, gate, decision, approver, timestamp, notes.

**Borrowed from:**

- OpenAI Agents: tracing, sessions, guardrails, handoffs.
- Google ADK: workflow/task runtime separation.
- EvoMap: events as auditable evolution records.

**Tests:**

- Store can create task/run/tool-call records.
- Tool args are summarized or hashed, not stored with secrets.
- Approval state blocks higher-autonomy actions by default.
- Trace export is deterministic JSON.

**Exit criteria:**

- LiMa can record an agent task without executing code.
- Every future autonomous action has a place to log evidence.

---

## Phase 3: Role Specs And Structured Outputs

**Purpose:** Make agents boring, typed, and reviewable.

**Create module:**

```text
agent_workbench/
  schemas.py
  planner.py
  reviewer.py
  tester.py
  memory_agent.py
```

**Role contracts:**

- Planner returns planned files, test commands, risks, and approval gates.
- Coder returns patch intent, touched files, and assumptions.
- Reviewer returns findings ordered by severity.
- Tester returns commands, exit codes, summaries, and artifacts.
- Memory/Evolution returns candidate lesson plus validation evidence.

**Borrowed from:**

- `agency-agents`: role clarity and success metrics.
- OpenAI Agents: handoff contracts and guardrails.
- ADK Task API: structured delegation.

**Tests:**

- Invalid role output is rejected.
- Missing test plan blocks implementation.
- Reviewer output without file evidence is marked incomplete.
- Memory candidate without validation evidence is not promoted.

**Exit criteria:**

- A single request can be planned and reviewed as structured data.
- No agent can silently skip tests or approval gates.

---

## Phase 4: Sequential Local Agent Loop

**Purpose:** Start with a simple loop before DAG orchestration.

**Create module:**

```text
agent_workbench/
  loop.py
  gates.py
```

**Loop:**

```text
owner request
  -> planner
  -> approval check
  -> coder
  -> tester
  -> reviewer
  -> fix loop, max 2 attempts
  -> final evidence summary
  -> optional memory/evolution candidate
```

**Rules:**

- Max attempts per phase: 2.
- No repeated identical failing command without changed hypothesis.
- No deploy, push, or destructive action.
- Reviewer must be separate from Coder.

**Tests:**

- Loop stops at approval gate for L3/L4 actions.
- Loop stops after max attempts and records failure.
- Tester failure flows back to Coder with captured output.
- Reviewer P0/P1 finding blocks completion.

**Exit criteria:**

- LiMa can run a local-only plan-code-test-review loop on a tiny controlled task.
- Every step is visible in the workbench trace.

---

## Phase 5: Skill And Gene Memory

**Purpose:** Add self-improvement without pretending it is magic.

**Create module:**

```text
agent_evolution/
  __init__.py
  skill_store.py
  gene_store.py
  extractor.py
  validator.py
  promoter.py
```

**Skill vs gene distinction:**

- Skill: human-readable SOP for a repeated task.
- Gene: compact machine-readable strategy cue with trigger signals and validation command.
- Event: append-only record of extraction, validation, promotion, rollback, or rejection.

**Borrowed from:**

- GenericAgent: crystallize successful task paths into reusable skills.
- EvoMap Evolver: Genes, Capsules, Events, validation before promotion.
- always-on-memory-agent: background consolidation and source-backed memory.

**Promotion rule:**

A candidate can be promoted only when:

- The task succeeded.
- Tests or verification commands passed.
- The candidate has trigger signals.
- The candidate has a rollback or rejection path.
- The owner approves automatic use, or it stays suggestion-only.

**Tests:**

- Failed tasks cannot produce promoted genes.
- Candidate with unsafe validation command is rejected.
- Event log is append-only.
- Skill/gene retrieval returns small cited snippets, not full logs.

**Exit criteria:**

- LiMa can learn reusable local patterns from successful sessions.
- Learned assets are auditable and removable.

---

## Phase 6: Multi-Agent DAG Runtime

**Purpose:** Add real "agent team" behavior only after the sequential loop works.

**Create module:**

```text
agent_workbench/
  workflow.py
  dag.py
  scheduler.py
  merge_queue.py
```

**Borrowed from:**

- Google ADK: graph runtime, routing, fan-out/fan-in, loops, retry, state.
- OpenAI Agents: handoffs and tracing.
- Autonomous-loop/Ralph pattern: work units, isolated review, merge queue.

**DAG rules:**

- Decompose into work units with explicit dependencies.
- Prefer fewer, cohesive units.
- Avoid parallel edits to the same file unless merge queue can serialize landing.
- Each unit includes its own tests.
- Large tasks require research, plan, implement, test, review, fix, final review.

**Tests:**

- DAG rejects cycles.
- Scheduler runs independent units in dependency layers.
- File-overlap detector serializes conflicting units.
- Failed unit captures test output and does not land.

**Exit criteria:**

- LiMa can coordinate several local work units without losing traceability.
- Parallelism is used only when file overlap and dependencies are safe.

---

## Phase 7: GitHub And VPS Boundaries

**Purpose:** Let LiMa help with remote work without handing it the keys casually.

**GitHub capabilities, gated:**

- Read issues, branches, PR checks, and CI logs.
- Prepare branch and PR description.
- Push or create PR only after explicit approval.

**VPS capabilities, gated:**

- Read health endpoints.
- Prepare deployment checklist.
- Deploy only after explicit owner approval.
- Always backup, compile, restart, health, authenticated smoke, rollback note.

**Tests/checks:**

- No GitHub token appears in trace, prompt, logs, or docs.
- Dry-run mode is available for every remote action.
- Approval record is required before push/deploy action.

**Exit criteria:**

- LiMa can prepare remote operations.
- Owner stays in control of state-changing remote actions.

---

## Phase 8: Admin UI And Operator Controls

**Purpose:** Make autonomy inspectable.

**Add admin views later:**

- Agent tasks list.
- Run trace timeline.
- Tool-call audit.
- Patch/test summary.
- Skill/gene candidates and promotion controls.
- Approval queue.

**Rules:**

- Admin API remains private.
- Query-token login hardening should be resolved before exposing sensitive agent traces.
- Do not show secrets or full prompt payloads by default.

**Exit criteria:**

- Owner can see what the agent did, why, with which files and tests.
- Owner can approve, pause, reject, or rollback learned behavior.

---

## Implementation Order

Recommended order for the owner:

1. Phase 0: Reference notes and documentation status.
2. Phase 1: Retrieval injection and typed memory recall.
3. Phase 2: Agent workbench ledger.
4. Phase 3: Role specs and structured outputs.
5. Phase 4: Sequential local loop.
6. Phase 5: Skill/gene memory.
7. Phase 6: DAG runtime.
8. Phase 7: GitHub/VPS gated operations.
9. Phase 8: Admin UI controls.

This order matters. A multi-agent loop without retrieval, memory, ledger, and tests will look impressive but be hard to trust.

---

## Verification Gate

Before marking any implementation phase complete:

```powershell
git -C D:\GIT diff --check
D:\GIT\venv\Scripts\python.exe -m py_compile <touched-python-files>
D:\GIT\venv\Scripts\python.exe -m pytest <new-or-focused-tests> -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest tests .\test_routing_engine.py .\test_rate_limiter.py .\test_http_caller.py .\test_dual_track.py .\test_code_orchestrator.py .\test_streaming.py .\test_skills_injector.py --ignore=active_model
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT
```

Notes:

- The target suite is the meaningful LiMa suite in this workspace.
- Unrestricted full-repo pytest can collect unrelated local reference repos and should not be used as the main signal.
- If the secret scan reports historical or unrelated files, classify them carefully; do not paste real secret values into docs or chat.

---

## Success Criteria

LiMa reaches the next meaningful height when:

- It can ground coding requests with traceable code and memory context.
- It can plan, patch, test, and review local changes under approval gates.
- It can explain every autonomous action in a ledger.
- It can promote only validated lessons into reusable skills/genes.
- It can prepare GitHub/VPS work, but state-changing remote operations remain owner-approved.

This is the realistic road from "smart router" to "controlled autonomous coding partner." It is not yet Opus-level cognition by itself, but it gives whatever model LiMa routes to a much stronger body: memory, tools, workflow, tests, and self-improvement rails.
