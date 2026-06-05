# LiMa Capability Hardening Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Use `safety-guard` before VPS deploy, external network changes, shell-capable worker changes, device/hardware operations, GitHub/Gitee writes, or credential handling. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn LiMa's broad but uneven capability set into a small number of reliable, daily-usable production loops with fresh evidence, operator visibility, and rollback paths.

**Architecture:** Keep LiMa Server as the control plane for routing, memory, task contracts, device tasks, ops, and deployment evidence. Hardening happens through narrow milestone slices: each slice adds one measurable capability, one regression harness, one smoke path, and one documentation closeout. New behavior remains default-off until tests, VPS smoke, and operator review prove it improves real productivity.

**Tech Stack:** Python 3.10+ FastAPI LiMa Server, pytest/Hypothesis/Pyright/Ruff/security gates, `deepcode-cli` TypeScript LiMa submodule, Redis-backed Device Gateway, existing MCP/search/memory tooling, Telegram/operator surfaces, VPS deployment scripts under `scripts/`.

---

## Diagnosis

LiMa is not weak across the board. The engineering substrate is already strong: routing layers, tests, VPS smoke discipline, Device Gateway protocol, Agent Task APIs, LiMa artifacts, MCP tools, learning loop, and observability scaffolds all exist.

The weak point is **closure density**: too many capable pieces exist side-by-side, while the two or three highest-frequency user paths still need to feel boringly reliable.

Hardening must therefore optimize for:

| Area | Current State | Weakness To Close | Success Signal |
|---|---|---|---|
| Chat/IDE coding | OpenAI/Anthropic-compatible routes, context preflight, routing tiers | Route quality and fallback evidence is scattered across docs, logs, and eval JSON | One golden-path smoke shows route, backend, latency, fallback, retrieval, memory, and closeout |
| LiMa Worker | `/agent/tasks`, artifact bundles, `/lima work`, learning loop | Worker prompt/hook/review loop is not yet the default daily production loop | One public task can be planned, executed, reviewed, learned from, and closed with artifacts |
| Device Gateway | Public Redis HA path, fake-U8, path pipeline, metrics | Fake loop is good; real-device release evidence is still pending | Fake smoke remains green, and real-device smoke has a gated repeatable checklist |
| Backend routing | SCNet/Kimi/Cloudflare/GitHub tiers and evals exist | Availability changes faster than static docs | Re-eval pipeline creates signed/dated admission evidence before promotion |
| Ops/learning | Metrics, memory, learning loop, Telegram commands | Operator has many endpoints but no single "what should I fix next" cockpit | Daily digest ranks failing loops by impact and points to evidence |
| Code quality | Large suite, CI gates, module split work | Remaining complexity is spread across routes and operator surfaces | Each hardening slice reduces risk without broad rewrites |

## Non-Goals

- Do not restart commercial platform, billing, quota sales, public registration, or customer dashboard work.
- Do not add new model providers to hot routing without admission evidence.
- Do not enable always-on worker, write-capable MCP tools, external shell/network execution, or hardware motion by default.
- Do not create a decorative dashboard before the evidence data exists.
- Do not replace `routing_engine.route()` or the explicit request pipeline with a new framework.

## Execution Order

The work should be done in seven slices. Each slice is independently shippable.

```text
M0 scorecard baseline
  -> M1 unified golden-path evidence
  -> M2 Chat/IDE reliability closure
  -> M3 LiMa worker daily loop
  -> M4 backend re-eval and admission closure
  -> M5 Device fake-to-real release gate
  -> M6 operator digest and closeout automation
```

M0 and M1 are prerequisites. M2, M3, M4, and M5 can then run in parallel if separate workers are available. M6 should wait until at least two production loops emit the unified evidence from M1.

## Shared Definitions

### Capability Score

Use a 0-5 score for each production loop:

| Score | Meaning | Evidence Required |
|---:|---|---|
| 0 | Not implemented | No route or command exists |
| 1 | Local prototype | Local unit/focused tests only |
| 2 | Integrated locally | Full relevant local tests pass |
| 3 | VPS deployed | VPS restart and `/health` pass |
| 4 | Public smoke | Public HTTPS/API smoke passes |
| 5 | Daily reliable | Recent repeatable smoke plus operator digest and rollback note |

### Unified Evidence Record

Every golden path should be able to produce this shape:

```json
{
  "schema_version": "lima.capability_evidence.v0",
  "loop": "chat_ide|lima_worker|device_gateway|backend_eval|ops_learning",
  "request_id": "string",
  "task_id": "optional-string",
  "device_id": "optional-string",
  "entrypoint": "route-or-command",
  "selected_backend": "optional-backend",
  "fallback_used": false,
  "latency_ms": 0,
  "status": "ok|needs_review|failed|blocked",
  "evidence": ["test-or-smoke-name"],
  "artifact_paths": ["relative/path"],
  "rollback": "short rollback note",
  "created_at": 0.0
}
```

This record is evidence-only. It must not automatically mutate routing pools, prompts, worker permissions, or device behavior.

---

## Milestone 0: Capability Scorecard Baseline

**Goal:** Create one current-state scorecard so future work improves measured loops instead of adding unrelated features.

**Files:**
- Create: `docs/CAPABILITY_HARDENING_SCORECARD.md`
- Modify: `docs/NEXT_MILESTONES.md`
- Modify: `docs/DOCUMENTATION_STATUS.md`
- Read only: `STATUS.md`, `docs/LIMA_MEMORY.md`, `findings.md`, `progress.md`

- [ ] **Step 1: Create the scorecard document**

  Create `docs/CAPABILITY_HARDENING_SCORECARD.md` with these sections:

  ```markdown
  # LiMa Capability Hardening Scorecard

  > Updated: 2026-05-26
  > Authority: `STATUS.md`, `docs/LIMA_MEMORY.md`, `docs/NEXT_MILESTONES.md`, `findings.md`, `progress.md`

  ## Scoring

  | Score | Meaning |
  |---:|---|
  | 0 | Not implemented |
  | 1 | Local prototype |
  | 2 | Integrated locally |
  | 3 | VPS deployed |
  | 4 | Public smoke |
  | 5 | Daily reliable |

  ## Current Scores

  | Loop | Score | Evidence | Next Gate |
  |---|---:|---|---|
  | Chat/IDE coding | 4 | `/v1/chat/completions`, `/v1/messages`, routing tiers, public smokes | Unified evidence record + reliability smoke |
  | LiMa Worker | 3 | `/agent/tasks`, public task smoke, artifact bundles | Prompt contract + hooks + review loop |
  | Device Gateway | 4 fake / 2 real | Redis HA, fake-U8 public WSS smoke | Real-device flash + motion smoke |
  | Backend routing | 4 | SCNet/Kimi/Cloudflare eval docs and JSON | Scheduled re-eval + admission report |
  | Ops/learning | 3 | learning loop, metrics, Telegram commands | Operator digest ranks next fixes |
  | Code quality | 4 | large suite, CI gates, module splits | Slice-level risk burn-down |
  ```

- [ ] **Step 2: Link the scorecard from milestone docs**

  Add one row to `docs/NEXT_MILESTONES.md` under related docs:

  ```markdown
  | `docs/CAPABILITY_HARDENING_SCORECARD.md` | Capability scorecard for deciding which weak production loop to harden next. |
  ```

  Add one row to `docs/DOCUMENTATION_STATUS.md` in the active planning/status area:

  ```markdown
  | `docs/CAPABILITY_HARDENING_SCORECARD.md` | Active scorecard | Ranks Chat/IDE, LiMa, Device Gateway, backend routing, ops/learning, and code quality by evidence level. |
  ```

- [ ] **Step 3: Verify docs-only change**

  Run:

  ```powershell
  git diff --check -- docs\CAPABILITY_HARDENING_SCORECARD.md docs\NEXT_MILESTONES.md docs\DOCUMENTATION_STATUS.md
  ```

  Expected: no whitespace errors.

- [ ] **Step 4: Commit**

  ```powershell
  git add docs\CAPABILITY_HARDENING_SCORECARD.md docs\NEXT_MILESTONES.md docs\DOCUMENTATION_STATUS.md
  git commit -m "docs: add LiMa capability hardening scorecard"
  ```

## Milestone 1: Unified Golden-Path Evidence

**Goal:** Add a tiny evidence API used by Chat/IDE, LiMa Worker, Device Gateway, backend eval, and ops learning.

**Files:**
- Create: `observability/capability_evidence.py`
- Create: `tests/test_capability_evidence.py`
- Modify: `routes/chat_post_closeout.py`
- Modify: `routes/agent_tasks.py`
- Modify: `routes/device_gateway.py`
- Modify: `scripts/run_eval_full_and_report.py`
- Modify: `routes/ops_metrics.py`

- [ ] **Step 1: Write evidence model tests first**

  Create `tests/test_capability_evidence.py` with tests for:

  ```python
  def test_record_evidence_redacts_secret_like_values(tmp_path, monkeypatch):
      monkeypatch.setenv("LIMA_CAPABILITY_EVIDENCE_PATH", str(tmp_path / "evidence.jsonl"))
      from observability.capability_evidence import record_evidence, recent_evidence

      record_evidence(
          loop="chat_ide",
          request_id="req-1",
          entrypoint="/v1/chat/completions",
          selected_backend="scnet_ds_flash",
          status="ok",
          evidence=["Bearer sk-test-123"],
      )

      row = recent_evidence(limit=1)[0]
      assert row["loop"] == "chat_ide"
      assert row["status"] == "ok"
      assert "sk-test" not in str(row)


  def test_record_evidence_caps_artifact_paths(tmp_path, monkeypatch):
      monkeypatch.setenv("LIMA_CAPABILITY_EVIDENCE_PATH", str(tmp_path / "evidence.jsonl"))
      from observability.capability_evidence import record_evidence, recent_evidence

      record_evidence(
          loop="lima_worker",
          request_id="req-2",
          task_id="task-2",
          entrypoint="/agent/tasks/task-2/result",
          status="needs_review",
          artifact_paths=[f"a{i}.md" for i in range(20)],
      )

      row = recent_evidence(limit=1)[0]
      assert len(row["artifact_paths"]) == 10
  ```

- [ ] **Step 2: Run tests and confirm red**

  ```powershell
  python -m pytest -q tests\test_capability_evidence.py --ignore=active_model
  ```

  Expected: import failure for `observability.capability_evidence`.

- [ ] **Step 3: Implement evidence module**

  Create `observability/capability_evidence.py`:

  ```python
  from __future__ import annotations

  import json
  import os
  import time
  from pathlib import Path
  from typing import Any

  from session_memory.redact import redact_text

  DEFAULT_PATH = Path("data/capability_evidence.jsonl")
  ALLOWED_LOOPS = {
      "chat_ide",
      "lima_worker",
      "device_gateway",
      "backend_eval",
      "ops_learning",
  }

  def _store_path() -> Path:
      return Path(os.environ.get("LIMA_CAPABILITY_EVIDENCE_PATH", str(DEFAULT_PATH)))

  def _clean(value: Any) -> Any:
      if isinstance(value, str):
          return redact_text(value)[:500]
      if isinstance(value, list):
          return [_clean(v) for v in value[:10]]
      if isinstance(value, dict):
          return {str(k)[:80]: _clean(v) for k, v in list(value.items())[:50]}
      if isinstance(value, (int, float, bool)) or value is None:
          return value
      return redact_text(str(value))[:500]

  def record_evidence(
      *,
      loop: str,
      request_id: str = "",
      task_id: str = "",
      device_id: str = "",
      entrypoint: str = "",
      selected_backend: str = "",
      fallback_used: bool = False,
      latency_ms: int = 0,
      status: str = "ok",
      evidence: list[str] | None = None,
      artifact_paths: list[str] | None = None,
      rollback: str = "",
  ) -> dict[str, Any]:
      if loop not in ALLOWED_LOOPS:
          raise ValueError(f"unsupported capability loop: {loop}")
      row = {
          "schema_version": "lima.capability_evidence.v0",
          "loop": loop,
          "request_id": _clean(request_id),
          "task_id": _clean(task_id),
          "device_id": _clean(device_id),
          "entrypoint": _clean(entrypoint),
          "selected_backend": _clean(selected_backend),
          "fallback_used": bool(fallback_used),
          "latency_ms": max(0, int(latency_ms or 0)),
          "status": _clean(status),
          "evidence": _clean(evidence or []),
          "artifact_paths": _clean(artifact_paths or []),
          "rollback": _clean(rollback),
          "created_at": time.time(),
      }
      path = _store_path()
      path.parent.mkdir(parents=True, exist_ok=True)
      with path.open("a", encoding="utf-8") as fh:
          fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
      return row

  def recent_evidence(*, limit: int = 20) -> list[dict[str, Any]]:
      path = _store_path()
      if not path.exists():
          return []
      rows = []
      for line in path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 100)):]:
          try:
              rows.append(json.loads(line))
          except json.JSONDecodeError:
              continue
      return rows
  ```

- [ ] **Step 4: Run evidence tests**

  ```powershell
  python -m pytest -q tests\test_capability_evidence.py --ignore=active_model
  ```

  Expected: `2 passed`.

- [ ] **Step 5: Wire chat closeout evidence**

  In `routes/chat_post_closeout.py`, after successful route closeout, call:

  ```python
  from observability.capability_evidence import record_evidence

  record_evidence(
      loop="chat_ide",
      request_id=request_id,
      entrypoint="/v1/chat/completions",
      selected_backend=backend,
      fallback_used=fallback_used,
      latency_ms=duration_ms,
      status="ok",
      evidence=["chat_post_closeout"],
  )
  ```

  If the current function names differ, keep the call at the boundary where backend, latency, and request status are already known. Catch only local evidence-write exceptions and log a warning; do not break chat responses.

- [ ] **Step 6: Wire worker result evidence**

  In `routes/agent_tasks.py` inside `submit_task_result()`, after learning-loop ingest attempt, call:

  ```python
  from observability.capability_evidence import record_evidence

  record_evidence(
      loop="lima_worker",
      request_id=task_id,
      task_id=task_id,
      entrypoint=f"/agent/tasks/{task_id}/result",
      selected_backend=body.backend or "",
      latency_ms=body.latency_ms or 0,
      status=result.status,
      evidence=["agent_task_result"],
      artifact_paths=body.artifacts,
      rollback="review task result and quarantine task if unsafe",
  )
  ```

- [ ] **Step 7: Wire device task evidence**

  In `routes/device_gateway.py`, record evidence when `/device/v1/tasks` returns queued/sent/failed:

  ```python
  from observability.capability_evidence import record_evidence

  record_evidence(
      loop="device_gateway",
      request_id=str(task.get("request_id", "")),
      task_id=str(task.get("task_id", "")),
      device_id=device_id,
      entrypoint="/device/v1/tasks",
      status="sent" if sent else "queued",
      evidence=["device_task_created"],
      rollback="delete pending task queue for test device if smoke-generated",
  )
  ```

  For validation-failed tasks, status must be `"failed"` and no queue mutation should occur.

- [ ] **Step 8: Wire backend eval evidence**

  In `scripts/run_eval_full_and_report.py`, after a successful report is written, call:

  ```python
  from observability.capability_evidence import record_evidence

  record_evidence(
      loop="backend_eval",
      request_id=report_path.name,
      entrypoint="scripts/run_eval_full_and_report.py",
      status="ok",
      evidence=[str(report_path)],
      artifact_paths=[str(report_path)],
      rollback="do not promote backend without admission review",
  )
  ```

- [ ] **Step 9: Expose recent evidence in ops metrics**

  In `routes/ops_metrics.py`, add a `capability_evidence` block:

  ```python
  from observability.capability_evidence import recent_evidence

  payload["capability_evidence"] = {
      "recent": recent_evidence(limit=10),
  }
  ```

  If the module cannot import, expose `{"recent": [], "error": "unavailable"}` and log a warning.

- [ ] **Step 10: Run focused tests**

  ```powershell
  python -m pytest -q tests\test_capability_evidence.py tests\test_chat_handler.py tests\test_agent_task_routes.py tests\test_device_gateway_routes.py tests\test_ops_metrics.py --ignore=active_model
  ```

  Expected: all focused tests pass.

- [ ] **Step 11: Run full local verification**

  ```powershell
  python -m pytest -q --ignore=active_model
  python scripts/run_pyright.py
  git diff --check
  ```

  Expected: full suite pass, Pyright clean, no diff whitespace errors.

- [ ] **Step 12: Commit**

  ```powershell
  git add observability\capability_evidence.py tests\test_capability_evidence.py routes\chat_post_closeout.py routes\agent_tasks.py routes\device_gateway.py routes\ops_metrics.py scripts\run_eval_full_and_report.py
  git commit -m "feat(observability): record unified capability evidence"
  ```

## Milestone 2: Chat/IDE Reliability Closure

**Goal:** Make one Chat/IDE request explainable end-to-end: auth, body limit, preflight, retrieval, backend choice, fallback, response, closeout, evidence.

**Files:**
- Create: `tests/test_chat_ide_golden_path.py`
- Modify: `routes/chat_preflight.py`
- Modify: `routing_engine.py`
- Modify: `routes/chat_post_closeout.py`
- Modify: `scripts/smoke_online_distributions.py`

- [ ] **Step 1: Add golden-path test**

  Create `tests/test_chat_ide_golden_path.py` with a mocked backend call and assertions that:

  - private auth is required;
  - request-local context is injected for IDE-like source;
  - routing returns a non-empty answer;
  - capability evidence is recorded;
  - no raw prompt secrets are persisted.

- [ ] **Step 2: Add smoke flag**

  Extend `scripts/smoke_online_distributions.py` with `--golden-path-evidence`. The flag should call public `/v1/chat/completions`, then authenticated `/v1/ops/metrics`, and assert `capability_evidence.recent` contains a `loop="chat_ide"` row created after the smoke started.

- [ ] **Step 3: Verify locally**

  ```powershell
  python -m pytest -q tests\test_chat_ide_golden_path.py tests\test_request_context_preflight.py tests\test_production_retrieval.py tests\test_route_post_process.py --ignore=active_model
  ```

- [ ] **Step 4: Deploy only after full suite**

  ```powershell
  python -m pytest -q --ignore=active_model
  python scripts/deploy_vps_bundle.py --smoke
  python scripts/smoke_online_distributions.py --api-key $env:LIMA_API_KEY --chat-exact golden_path_ok --golden-path-evidence
  ```

- [ ] **Step 5: Close out docs**

  Update `progress.md`, `findings.md`, and `docs/CAPABILITY_HARDENING_SCORECARD.md`:

  ```markdown
  | Chat/IDE coding | 5 | Golden-path evidence smoke passed on public HTTPS | Keep monitoring fallback and latency |
  ```

## Milestone 3: LiMa Worker Daily Loop

**Goal:** Make a LiMa task run produce a reviewable artifact bundle, submit `needs_review`, enter learning loop, and appear in capability evidence.

**Files:**
- Modify: `docs/LIMA_MANAGEMENT.md`
- Modify: `routes/agent_task_schemas.py`
- Modify: `routes/agent_task_service.py`
- Modify: `routes/agent_tasks.py`
- Modify: `deepcode-cli` submodule files for prompt contract and hooks
- Create: `tests/test_lima_daily_loop.py`
- Use existing: `scripts/smoke_lcw1_prompt_contract_e2e.py`, `scripts/smoke_lcw2_hooks_e2e.py`, `scripts/smoke_prod008_learning_loop_e2e.py`

- [ ] **Step 1: Lock Task Prompt Contract v0.1**

  Ensure every task has these fields at the Server boundary:

  ```text
  Context
  Task
  Constraints
  Verify
  Output
  ```

  Add tests that reject task prompts missing `Verify` or `Output` when mode is `patch`, `review`, or `ship`.

- [ ] **Step 2: Wire hook evidence**

  In LiMa, hooks must write a per-task local evidence file:

  ```json
  {
    "schema_version": "lima.hook_evidence.v0",
    "task_id": "string",
    "touched_files": [],
    "tests_run": [],
    "failures": [],
    "review_required": true
  }
  ```

  Do not submit this automatically until the task result is created; include it as an artifact path.

- [ ] **Step 3: Verify LiMa submodule first**

  ```powershell
  cd D:\GIT\deepcode-cli
  npm.cmd test
  npm.cmd run check
  ```

- [ ] **Step 4: Verify Server integration**

  ```powershell
  cd D:\GIT
  python -m pytest -q tests\test_agent_task_contract.py tests\test_agent_task_routes.py tests\test_lima_daily_loop.py tests\test_learning_loop.py --ignore=active_model
  ```

- [ ] **Step 5: VPS smoke**

  ```powershell
  python scripts/deploy_lcw1_e2e_slice.py
  python scripts/smoke_lcw1_prompt_contract_e2e.py
  python scripts/smoke_lcw2_hooks_e2e.py
  python scripts/smoke_prod008_learning_loop_e2e.py
  ```

- [ ] **Step 6: Close out**

  Update:

  - `docs/LIMA_MANAGEMENT.md`
  - `docs/CAPABILITY_HARDENING_SCORECARD.md`
  - `STATUS.md`
  - `docs/LIMA_MEMORY.md`
  - `progress.md`
  - `findings.md`

  Commit submodule first, then main repo pointer:

  ```powershell
  cd D:\GIT\deepcode-cli
  git status --short
  git add <only-related-files>
  git commit -m "feat(lima): add daily worker hook evidence"
  git push origin HEAD

  cd D:\GIT
  git add deepcode-cli docs\LIMA_MANAGEMENT.md docs\CAPABILITY_HARDENING_SCORECARD.md STATUS.md docs\LIMA_MEMORY.md progress.md findings.md tests\test_lima_daily_loop.py
  git commit -m "feat(agent): close LiMa daily worker loop"
  python scripts/push_dual_remotes.py
  ```

## Milestone 4: Backend Re-Eval And Admission Closure

**Goal:** Convert backend routing from "docs say this works" to "dated re-eval evidence controls promotion".

**Files:**
- Modify: `scripts/eval_coding_backends.py`
- Modify: `backend_admission_store.py`
- Modify: `route_scorer.py`
- Modify: `docs/FREE_MODEL_ROUTING_STATUS.md`
- Modify: `docs/CODING_BACKEND_RANKING.md`
- Create: `tests/test_backend_admission_from_eval.py`

- [ ] **Step 1: Add eval-to-admission test**

  The test should load a small fixture with:

  ```json
  [
    {"backend": "candidate_fast", "passes": 3, "total": 3, "avg_score": 100, "avg_latency_ms": 900},
    {"backend": "candidate_slow", "passes": 3, "total": 3, "avg_score": 100, "avg_latency_ms": 12000},
    {"backend": "candidate_bad", "passes": 1, "total": 3, "avg_score": 40, "avg_latency_ms": 500}
  ]
  ```

  Assert:

  - `candidate_fast` becomes `medium` or better only if `private_code_allowed=true`;
  - `candidate_slow` is deep/fallback only;
  - `candidate_bad` is inactive;
  - no admission change is applied without a dated report path.

- [ ] **Step 2: Add report signature fields**

  Every eval report should include:

  ```json
  {
    "created_at": "ISO-8601",
    "runner": "scripts/eval_coding_backends.py",
    "topology": "vps|windows_local|frp",
    "private_code_allowed": false,
    "promotion_recommendations": []
  }
  ```

- [ ] **Step 3: Keep promotion explicit**

  `backend_admission_store.py` may read recommendations, but route pools must not change until a human/operator applies the admission overlay.

- [ ] **Step 4: Verify**

  ```powershell
  python -m pytest -q tests\test_coding_eval.py tests\test_backend_admission_overlay.py tests\test_backend_admission_from_eval.py tests\test_route_scorer.py --ignore=active_model
  python scripts/eval_coding_backends.py
  ```

- [ ] **Step 5: Docs closeout**

  Update `docs/FREE_MODEL_ROUTING_STATUS.md` and `docs/CODING_BACKEND_RANKING.md` with the exact command, backend count, pass counts, latency, and admission decision. Do not edit routing pools in the same commit unless the eval gate explicitly approves it.

## Milestone 5: Device Gateway Fake-To-Real Release Gate

**Goal:** Keep fake-device confidence, then add a repeatable real-device checklist without pretending fake evidence is hardware evidence.

**Files:**
- Modify: `docs/ESP32S_XYZ_MANAGEMENT.md`
- Modify: `docs/LIMA_REAL_MACHINE_SMOKE.md`
- Modify: `scripts/smoke_wokwi_device_loop.py`
- Modify: `scripts/smoke_device_gateway_public.py`
- Create: `tests/test_device_release_gate.py`
- Potential submodule changes: `esp32S_XYZ/tools/fake_lima_u8/`

- [ ] **Step 1: Add release-gate test**

  Add `tests/test_device_release_gate.py` that asserts a release checklist cannot mark real hardware complete unless evidence contains:

  - firmware build or flash evidence;
  - public `/device/v1/health`;
  - fake-U8 WSS smoke;
  - real-device `write` task result;
  - real-device `home` or `stop` control result;
  - rollback note.

- [ ] **Step 2: Strengthen fake smoke**

  Extend fake smoke output to record capability evidence with:

  ```text
  loop=device_gateway
  status=ok
  evidence=fake_u8_wss_success
  ```

- [ ] **Step 3: Add real smoke checklist**

  In `docs/LIMA_REAL_MACHINE_SMOKE.md`, add an operator-run block:

  ```powershell
  python scripts/smoke_device_gateway_public.py --device-id <real-device-id> --send-write "write LiMa" --send-control home
  ```

  Required captured output:

  ```text
  health: ok
  write task: done
  control task: done
  motion events: progress, done
  rollback: disable device token or stop lima-router
  ```

- [ ] **Step 4: Verify fake path**

  ```powershell
  python -m pytest -q tests\test_device_gateway_routes.py tests\test_device_gateway_motion_contract.py tests\test_device_release_gate.py --ignore=active_model
  python scripts/smoke_wokwi_device_loop.py
  python scripts/smoke_device_gateway_public.py
  ```

- [ ] **Step 5: Real hardware gate**

  Do not claim release complete until the operator has a connected device and the real smoke command passes. If no device is connected, update `findings.md` with `real hardware pending` and keep score at fake 4 / real 2.

## Milestone 6: Operator Digest And Next-Fix Ranking

**Goal:** Give the operator one answer to "what is weak today and what should I fix next?"

**Files:**
- Create: `ops_entrypoint/capability_digest.py`
- Modify: `routes/ops_metrics.py`
- Modify: `routes/telegram_knowledge.py` or `routes/telegram_dispatch.py`
- Create: `tests/test_capability_digest.py`

- [ ] **Step 1: Add digest scoring tests**

  Test input:

  ```python
  evidence = [
      {"loop": "chat_ide", "status": "ok", "latency_ms": 1200},
      {"loop": "lima_worker", "status": "needs_review", "latency_ms": 0},
      {"loop": "device_gateway", "status": "failed", "latency_ms": 0},
  ]
  ```

  Expected top recommendation:

  ```text
  device_gateway: failed recent evidence, run fake smoke then real-device checklist
  ```

- [ ] **Step 2: Implement digest module**

  `ops_entrypoint/capability_digest.py` should expose:

  ```python
  def build_capability_digest(evidence: list[dict], *, limit: int = 5) -> dict:
      ...
  ```

  Return:

  ```json
  {
    "recommendations": [
      {"loop": "device_gateway", "priority": 100, "reason": "recent failure", "next_command": "python scripts/smoke_device_gateway_public.py"}
    ],
    "summary": {"ok": 1, "failed": 1, "needs_review": 1}
  }
  ```

- [ ] **Step 3: Expose through ops metrics**

  Add:

  ```json
  "capability_digest": {
    "recommendations": [],
    "summary": {}
  }
  ```

- [ ] **Step 4: Add Telegram operator command**

  Add `/digest` or extend existing digest command to include:

  ```text
  LiMa capability digest
  1. device_gateway - recent failure - run public/fake smoke
  2. lima_worker - needs_review - inspect latest task artifacts
  3. chat_ide - ok - monitor latency
  ```

- [ ] **Step 5: Verify**

  ```powershell
  python -m pytest -q tests\test_capability_digest.py tests\test_ops_metrics.py tests\test_telegram_knowledge.py --ignore=active_model
  python scripts/smoke_telegram_operator_vps.py
  ```

## Milestone 7: Release Train Closeout

**Goal:** Ship the hardening set only after local, VPS, public, and documentation evidence agree.

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `docs/CAPABILITY_HARDENING_SCORECARD.md`

- [ ] **Step 1: Run local full verification**

  ```powershell
  python -m pytest -q --ignore=active_model
  python scripts/run_pyright.py
  python scripts/run_ruff_check.py
  python scripts/run_security_gates.py
  git diff --check
  ```

- [ ] **Step 2: Deploy to VPS**

  Use the slice-appropriate deploy script. If multiple slices are bundled:

  ```powershell
  python scripts/deploy_vps_bundle.py --smoke
  ```

  Required VPS evidence:

  ```text
  systemctl is-active lima-router: active
  http://127.0.0.1:8080/health: status=ok
  public smoke: 12/12
  capability evidence: recent row for touched loop
  rollback: git commit hash or documented previous deploy point
  ```

- [ ] **Step 3: Run public smokes**

  ```powershell
  python scripts/smoke_online_distributions.py --api-key $env:LIMA_API_KEY --chat-exact capability_hardening_ok
  python scripts/smoke_retrieval_trace.py
  python scripts/smoke_device_gateway_public.py
  ```

  Run LiMa and Telegram smokes only if those slices changed:

  ```powershell
  python scripts/smoke_prod008_learning_loop_e2e.py
  python scripts/smoke_telegram_operator_vps.py
  ```

- [ ] **Step 4: Update closeout documents**

  Add a dated closeout section to:

  - `STATUS.md`
  - `docs/LIMA_MEMORY.md`
  - `progress.md`
  - `findings.md`
  - `docs/CAPABILITY_HARDENING_SCORECARD.md`

  Include:

  ```markdown
  - Commit:
  - Local tests:
  - Pyright/Ruff/security:
  - VPS backup or rollback point:
  - VPS health:
  - Public smokes:
  - Capability evidence rows:
  - Residual risks:
  ```

- [ ] **Step 5: Stage only related files**

  ```powershell
  git status --short
  git add <only-files-from-this-slice>
  git status --short
  ```

  Do not stage:

  ```text
  .env
  .coverage
  data/*.db
  data/private/*
  tmp_*.txt
  local reference repositories
  generated caches
  credentials
  ```

- [ ] **Step 6: Commit and push both remotes**

  ```powershell
  git commit -m "feat(ops): harden LiMa capability evidence loops"
  python scripts/push_dual_remotes.py
  ```

## Risk Register

| Risk | Trigger | Mitigation |
|---|---|---|
| Evidence write breaks hot path | JSONL path permission error | Catch local evidence exceptions, log warning, never fail chat/device/task response |
| Secret leakage into evidence | Prompts, tokens, artifact paths include credentials | Use `session_memory.redact.redact_text`, cap field lengths, include secret scan in closeout |
| Metrics endpoint becomes heavy | Ops metrics reads too much JSONL | Limit recent evidence to 10-20 rows; no full scans in request path |
| Worker loop becomes unsafe | Hooks or worker auto-submit too much | Keep repo allowlist, budget, stop marker, quarantine, review-required result |
| Fake device confused with real hardware | Scorecard marks Device complete too early | Track fake score and real score separately |
| Routing promotion becomes automatic | Eval recommendations mutate route pools | Admission reports are evidence-only until explicit apply |
| Dirty workspace causes accidental commit | Broad git add | Stage exact files only; inspect `git status --short` before commit |

## Verification Matrix

| Slice | Focused Tests | Full Tests | VPS/Public Smoke |
|---|---|---|---|
| M0 scorecard | `git diff --check` | Not required | None |
| M1 evidence | `tests/test_capability_evidence.py`, chat, agent, device, ops tests | Required | Deploy if hot path touched |
| M2 Chat/IDE | chat/preflight/retrieval/post-process tests | Required | online distributions + golden evidence |
| M3 LiMa | LiMa npm tests/check + agent task tests | Required | LCW prompt/hooks/learning smokes |
| M4 backend eval | coding eval/admission/route scorer tests | Required if route code changed | eval script; deploy only on routing apply |
| M5 Device | device route/motion/release tests | Required if server code changed | fake WSS; real hardware only when available |
| M6 digest | digest/ops/telegram tests | Required if routes changed | telegram operator smoke |
| M7 release | all relevant gates | Required | health + public 12/12 + loop smokes |

## Self-Review

- Spec coverage: The plan addresses the weak areas identified in discussion: main user experience, worker loop, hardware loop, backend volatility, ops visibility, and closeout discipline.
- Placeholder scan: No placeholder-marker or vague validation-only steps are used as implementation instructions. Every milestone names files, commands, expected evidence, and closeout criteria.
- Type consistency: The shared evidence record uses one schema name, one loop enum set, and the same field names across Chat/IDE, Worker, Device, Eval, and Ops tasks.
- Safety: New behavior is evidence-only by default. No routing, worker execution, device behavior, or MCP write surface is enabled merely by recording evidence.
