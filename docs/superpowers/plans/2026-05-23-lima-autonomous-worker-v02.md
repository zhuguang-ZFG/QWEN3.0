# LiMa Autonomous Worker v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the lifecycle layer LiMa needs before true daemon mode: stop control, failure quarantine, repository allowlist, runtime budget, audit UI, and real-repo smoke verification.

**Architecture:** LiMa Server remains the orchestrator and policy/audit source; LiMa Code remains the local executor that reads/writes only explicitly allowed repositories. This plan follows the GenericAgent/Evolver/agency-agents direction, but converts it into a controlled personal coding assistant: skills are candidates before activation, evolution is evidence-gated, and agent roles are limited to the coding workflow.

**Tech Stack:** Python 3.11, FastAPI, pytest, current `agent_contracts`, `routes.agent_tasks`, `agent_evolution`; TypeScript, Node.js, React Ink CLI, current `src/lima/*`, `src/ui/App.tsx`, `node:test`.

---

## Direction Calibration

This is the intended direction:

- GenericAgent-style skill growth: LiMa should turn repeated successful task patterns into reusable candidate skills.
- Evolver-style evolution protocol: LiMa should record every proposed improvement as an auditable candidate with evidence, regression results, and a promotion decision.
- agency-agents-style role library: LiMa should use a small set of focused roles for coding work instead of one giant prompt.

This is not the intended direction yet:

- No fully autonomous self-modification.
- No automatic production deployment.
- No unbounded local daemon.
- No 61-role agent company at startup.
- No Server-side shell execution.

LiMa v0.2 should be a controlled autonomous coding worker, not a fully autonomous evolution body.

## Current Baseline

Completed baseline:

- LiMa Server exposes agent task endpoints under `routes/agent_tasks.py`.
- LiMa Code supports `/lima task <task_id>`, `/lima next`, `/lima work --once`, and bounded `/lima work --loop --max-tasks <n>`.
- LiMa Code writes local audit entries to `.lima-code/audit.jsonl`.
- Public smoke verified Server task creation, worker polling, local execution, result submission, and event retrieval.

Known gaps this plan closes:

- A worker cannot be claimed with a lease.
- A task cannot be cancelled from Server once a worker starts it.
- Worker loops have no persistent stop marker.
- Repository authorization is implicit through workspace checks, not an explicit user allowlist.
- Failure backoff is local and transient; repeated failures are not quarantined.
- Runtime budgets are task-level but not worker-session-level.
- Audit exists as JSONL, but there is no user-facing audit view.
- Real-repo patch/test workflow is not yet proven end to end.

## File Structure

Server files:

- Modify: `agent_contracts/task_contract.py` - extend task status vocabulary and add lifecycle metadata fields.
- Modify: `routes/agent_tasks.py` - add claim, cancel, control, review, and quarantine endpoints.
- Modify: `tests/test_agent_task_contract.py` - cover extended statuses and lifecycle validation.
- Modify: `tests/test_agent_task_routes.py` - cover lifecycle endpoint behavior.
- Modify: `agent_evolution/candidates.py` - accept task evidence from reviewed successful tasks.
- Modify: `tests/test_agent_evolution.py` - prove reviewed task evidence creates inactive candidate skills only.

LiMa Code files:

- Create: `D:\GIT\deepcode-cli\src\lima\repo-allowlist.ts` - explicit repository authorization.
- Create: `D:\GIT\deepcode-cli\src\lima\worker-budget.ts` - worker-session budgets and counters.
- Create: `D:\GIT\deepcode-cli\src\lima\failure-quarantine.ts` - repeated failure tracking and quarantine decisions.
- Create: `D:\GIT\deepcode-cli\src\lima\worker-control.ts` - stop marker and run state.
- Create: `D:\GIT\deepcode-cli\src\lima\audit-reader.ts` - read and summarize `.lima-code/audit.jsonl`.
- Modify: `D:\GIT\deepcode-cli\src\lima\commands.ts` - parse lifecycle commands.
- Modify: `D:\GIT\deepcode-cli\src\lima\command-runner.ts` - use claim/control/budget/quarantine/audit commands.
- Modify: `D:\GIT\deepcode-cli\src\lima\agent-task-client.ts` - add claim, cancel/control polling, and task review calls.
- Modify: `D:\GIT\deepcode-cli\src\lima\workspace-guard.ts` - require explicit allowlist for non-current repos.
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-commands.test.ts` - command parser coverage.
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts` - lifecycle loop coverage.
- Create: `D:\GIT\deepcode-cli\src\tests\lima-repo-allowlist.test.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-worker-budget.test.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-failure-quarantine.test.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-worker-control.test.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-audit-reader.test.ts`

Docs:

- Modify: `STATUS.md` - update LiMa Code worker reality after implementation.
- Modify: `docs/LIMA_MEMORY.md` - append lifecycle/evolution decision record.
- Modify: `progress.md` - append implementation evidence and test results.

---

## Task 1: Extend Task Lifecycle Contract

**Files:**

- Modify: `agent_contracts/task_contract.py`
- Modify: `tests/test_agent_task_contract.py`
- Modify: `D:\GIT\deepcode-cli\src\lima\agent-task-types.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-agent-task-types.test.ts`

- [x] **Step 1: Write failing Server contract tests**

Add tests to `tests/test_agent_task_contract.py`:

```python
def test_agent_task_result_accepts_lifecycle_statuses():
    for status in [
        "accepted",
        "claimed",
        "running",
        "needs_review",
        "approved",
        "rejected",
        "applied",
        "succeeded",
        "failed",
        "blocked",
        "cancel_requested",
        "cancelled",
        "quarantined",
    ]:
        result = AgentTaskResult(
            task_id="task-life",
            status=status,
            summary=f"status {status}",
        )
        result.validate()


def test_agent_task_request_accepts_worker_lifecycle_metadata():
    req = AgentTaskRequest(
        task_id="task-life",
        repo="D:/GIT/deepcode-cli",
        branch="main",
        goal="review diff",
        allowed_tools=["git_diff"],
        max_runtime_sec=300,
        mode="review",
        worker_id="worker-local",
        lease_expires_at=123.0,
        cancel_requested=False,
        failure_count=0,
    )
    req.validate()
    assert req.worker_id == "worker-local"
```

- [x] **Step 2: Run failing Server tests**

Run:

```bash
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q
```

Expected: fails because lifecycle statuses and metadata fields do not exist yet.

- [x] **Step 3: Extend Python task contract**

Update `agent_contracts/task_contract.py`:

```python
VALID_STATUSES = (
    "accepted",
    "claimed",
    "running",
    "needs_review",
    "approved",
    "rejected",
    "applied",
    "succeeded",
    "failed",
    "blocked",
    "cancel_requested",
    "cancelled",
    "quarantined",
)


@dataclass
class AgentTaskRequest:
    task_id: str
    repo: str
    branch: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    max_runtime_sec: int = 300
    mode: Literal["plan", "patch", "test", "review"] = "patch"
    worker_id: str = ""
    lease_expires_at: float = 0.0
    cancel_requested: bool = False
    failure_count: int = 0

    def validate(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be one of {VALID_MODES}")
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if not self.repo:
            raise ValueError("repo must not be empty")
        if not self.branch:
            raise ValueError("branch must not be empty")
        if not self.goal:
            raise ValueError("goal must not be empty")
        if self.max_runtime_sec <= 0:
            raise ValueError("max_runtime_sec must be positive")
        if self.failure_count < 0:
            raise ValueError("failure_count must not be negative")
```

- [x] **Step 4: Write failing LiMa Code contract tests**

Add to `D:\GIT\deepcode-cli\src\tests\lima-agent-task-types.test.ts`:

```ts
test("validateLiMaAgentTaskRequest accepts lifecycle metadata", () => {
  const result = validateLiMaAgentTaskRequest({
    ...validRequest,
    worker_id: "worker-local",
    lease_expires_at: 123,
    cancel_requested: false,
    failure_count: 0,
  });
  assert.equal(result.ok, true);
});

test("validateLiMaAgentTaskResult accepts lifecycle statuses", () => {
  for (const status of [
    "claimed",
    "running",
    "approved",
    "rejected",
    "applied",
    "cancel_requested",
    "cancelled",
    "quarantined",
  ]) {
    const result = validateLiMaAgentTaskResult({ ...validResult, status });
    assert.equal(result.ok, true, status);
  }
});
```

- [x] **Step 5: Extend TypeScript task contract**

Update `D:\GIT\deepcode-cli\src\lima\agent-task-types.ts` with matching optional fields and statuses:

```ts
export const LIMA_AGENT_TASK_STATUSES = [
  "accepted",
  "claimed",
  "running",
  "needs_review",
  "approved",
  "rejected",
  "applied",
  "succeeded",
  "failed",
  "blocked",
  "cancel_requested",
  "cancelled",
  "quarantined",
] as const;

export type LiMaAgentTaskRequest = {
  task_id: string;
  repo: string;
  branch: string;
  goal: string;
  constraints: string[];
  allowed_tools: string[];
  max_runtime_sec: number;
  mode: LiMaAgentTaskMode;
  worker_id?: string;
  lease_expires_at?: number;
  cancel_requested?: boolean;
  failure_count?: number;
};
```

- [x] **Step 6: Run contract tests**

Run:

```bash
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py -q
npm.cmd test -- src/tests/lima-agent-task-types.test.ts
```

Expected: all selected contract tests pass.

- [x] **Step 7: Commit Task 1**

```bash
git add agent_contracts/task_contract.py tests/test_agent_task_contract.py
git commit -m "feat: extend agent task lifecycle contract"
```

Then in `D:\GIT\deepcode-cli`:

```bash
git add src/lima/agent-task-types.ts src/tests/lima-agent-task-types.test.ts
git commit -m "feat: align lima task lifecycle types"
```

---

## Task 2: Add Server Claim, Cancel, Control, and Review Gates

**Files:**

- Modify: `routes/agent_tasks.py`
- Modify: `tests/test_agent_task_routes.py`
- Modify: `agent_evolution/candidates.py`
- Modify: `tests/test_agent_evolution.py`

- [x] **Step 1: Write failing route lifecycle tests**

Add tests to `tests/test_agent_task_routes.py`:

```python
def test_claim_task_assigns_worker_and_lease(self):
    task_id = client.post("/agent/tasks", json={
        "repo": "D:/GIT/deepcode-cli",
        "goal": "review diff",
        "allowed_tools": ["git_diff"],
        "mode": "review",
    }, headers=HEADERS).json()["task_id"]

    resp = client.post(
        f"/agent/tasks/{task_id}/claim",
        json={"worker_id": "worker-local", "lease_sec": 60},
        headers=HEADERS,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["task"]["worker_id"] == "worker-local"
    assert data["status"] == "running"


def test_cancel_task_marks_control_flag(self):
    task_id = client.post("/agent/tasks", json={
        "repo": "D:/GIT/deepcode-cli",
        "goal": "test cancel",
        "allowed_tools": ["git_diff"],
        "mode": "review",
    }, headers=HEADERS).json()["task_id"]

    resp = client.post(f"/agent/tasks/{task_id}/cancel", headers=HEADERS)
    assert resp.status_code == 200

    control = client.get(f"/agent/tasks/{task_id}/control", headers=HEADERS)
    assert control.status_code == 200
    assert control.json()["cancel_requested"] is True


def test_review_gate_promotes_only_approved_successful_task(self):
    task_id = client.post("/agent/tasks", json={
        "repo": "D:/GIT/deepcode-cli",
        "goal": "safe patch",
        "allowed_tools": ["git_diff"],
        "mode": "review",
    }, headers=HEADERS).json()["task_id"]

    result = {
        "task_id": task_id,
        "status": "needs_review",
        "summary": "reviewed",
        "changed_files": [],
        "test_commands": [],
        "test_results": [],
        "diff_preview": "",
        "artifacts": [],
        "risks": [],
        "next_action": "approve",
    }
    client.post(f"/agent/tasks/{task_id}/result", json=result, headers=HEADERS)

    review = client.post(
        f"/agent/tasks/{task_id}/review",
        json={"decision": "approved", "reviewer": "human"},
        headers=HEADERS,
    )
    assert review.status_code == 200
    assert review.json()["status"] == "approved"
```

- [x] **Step 2: Run failing route tests**

Run:

```bash
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py -q
```

Expected: fails because `/claim`, `/cancel`, `/control`, and `/review` do not exist yet.

- [x] **Step 3: Add request bodies and helpers**

Update `routes/agent_tasks.py`:

```python
class ClaimBody(BaseModel):
    worker_id: str
    lease_sec: int = Field(default=300, ge=1, le=3600)


class ReviewBody(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: str = "human"
    note: str = ""


def _append_event(task_id: str, event: dict) -> None:
    event = {"ts": time.time(), **event}
    _events.setdefault(task_id, []).append(event)
    if task_id in _tasks:
        _tasks[task_id].setdefault("events", []).append(event)
```

- [x] **Step 4: Implement claim endpoint**

Add to `routes/agent_tasks.py`:

```python
@router.post("/tasks/{task_id}/claim", dependencies=[Depends(_require_admin)])
async def claim_task(task_id: str, body: ClaimBody):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    task = _tasks[task_id]
    if task["status"] not in ("accepted", "claimed", "running"):
        raise HTTPException(409, f"Task cannot be claimed from {task['status']}")
    now = time.time()
    request = dict(task["request"])
    request["worker_id"] = body.worker_id
    request["lease_expires_at"] = now + body.lease_sec
    request["cancel_requested"] = False
    task["request"] = request
    task["status"] = "running"
    task["updated_at"] = now
    _append_event(task_id, {"type": "claimed", "worker_id": body.worker_id})
    return _task_envelope(task)
```

- [x] **Step 5: Implement cancel and control endpoints**

Add to `routes/agent_tasks.py`:

```python
@router.post("/tasks/{task_id}/cancel", dependencies=[Depends(_require_admin)])
async def cancel_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    task = _tasks[task_id]
    request = dict(task["request"])
    request["cancel_requested"] = True
    task["request"] = request
    task["status"] = "cancel_requested"
    task["updated_at"] = time.time()
    _append_event(task_id, {"type": "cancel_requested"})
    return {"task_id": task_id, "status": "cancel_requested"}


@router.get("/tasks/{task_id}/control", dependencies=[Depends(_require_admin)])
async def get_task_control(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    request = _tasks[task_id]["request"]
    return {
        "task_id": task_id,
        "status": _tasks[task_id]["status"],
        "cancel_requested": bool(request.get("cancel_requested", False)),
        "lease_expires_at": float(request.get("lease_expires_at", 0.0)),
    }
```

- [x] **Step 6: Implement review gate**

Add to `routes/agent_tasks.py`:

```python
@router.post("/tasks/{task_id}/review", dependencies=[Depends(_require_admin)])
async def review_task(task_id: str, body: ReviewBody):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    task = _tasks[task_id]
    if "result" not in task:
        raise HTTPException(409, "Task has no worker result to review")
    if task["status"] != "needs_review":
        raise HTTPException(409, f"Task cannot be reviewed from {task['status']}")
    task["status"] = body.decision
    task["updated_at"] = time.time()
    _append_event(task_id, {
        "type": "reviewed",
        "decision": body.decision,
        "reviewer": body.reviewer,
        "note": body.note,
    })
    return {"task_id": task_id, "status": body.decision}
```

- [x] **Step 7: Run route tests**

Run:

```bash
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py tests\test_agent_evolution.py -q
```

Expected: selected tests pass.

- [x] **Step 8: Commit Task 2**

```bash
git add routes/agent_tasks.py tests/test_agent_task_routes.py agent_evolution/candidates.py tests/test_agent_evolution.py
git commit -m "feat: add agent task lifecycle gates"
```

---

## Task 3: Add Explicit Repository Allowlist

**Files:**

- Create: `D:\GIT\deepcode-cli\src\lima\repo-allowlist.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-repo-allowlist.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\workspace-guard.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-workspace-guard.test.ts`

- [x] **Step 1: Write failing allowlist tests**

Create `D:\GIT\deepcode-cli\src\tests\lima-repo-allowlist.test.ts`:

```ts
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { isRepoAllowed, normalizeAllowedRepos } from "../lima/repo-allowlist";

test("normalizeAllowedRepos resolves absolute directories", () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "lima-allowed-"));
  assert.deepEqual(normalizeAllowedRepos([repo]), [path.resolve(repo)]);
});

test("isRepoAllowed accepts the current workspace", () => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "lima-workspace-"));
  assert.equal(isRepoAllowed(workspace, { currentWorkspace: workspace, allowedRepos: [] }).ok, true);
});

test("isRepoAllowed rejects a sibling repo without explicit allowlist", () => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "lima-workspace-"));
  const sibling = fs.mkdtempSync(path.join(os.tmpdir(), "lima-sibling-"));
  const result = isRepoAllowed(sibling, { currentWorkspace: workspace, allowedRepos: [] });
  assert.equal(result.ok, false);
  assert.match(result.error, /not allowlisted/);
});

test("isRepoAllowed accepts configured additional repos", () => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "lima-workspace-"));
  const sibling = fs.mkdtempSync(path.join(os.tmpdir(), "lima-sibling-"));
  const result = isRepoAllowed(sibling, { currentWorkspace: workspace, allowedRepos: [sibling] });
  assert.equal(result.ok, true);
});
```

- [x] **Step 2: Run failing allowlist tests**

Run:

```bash
npm.cmd test -- src/tests/lima-repo-allowlist.test.ts
```

Expected: fails because `repo-allowlist.ts` does not exist.

- [x] **Step 3: Implement allowlist helper**

Create `D:\GIT\deepcode-cli\src\lima\repo-allowlist.ts`:

```ts
import path from "node:path";

export type LiMaRepoAllowlistConfig = {
  currentWorkspace: string;
  allowedRepos?: string[];
};

export type LiMaRepoAllowlistResult = { ok: true; value: string } | { ok: false; error: string };

export function normalizeAllowedRepos(repos: string[] = []): string[] {
  return repos.map((repo) => path.resolve(repo));
}

export function isRepoAllowed(repo: string, config: LiMaRepoAllowlistConfig): LiMaRepoAllowlistResult {
  const resolvedRepo = path.resolve(repo);
  const workspace = path.resolve(config.currentWorkspace);
  const allowed = [workspace, ...normalizeAllowedRepos(config.allowedRepos)];

  if (allowed.some((root) => isInsideOrSame(resolvedRepo, root))) {
    return { ok: true, value: resolvedRepo };
  }
  return { ok: false, error: `LiMa task repo is not allowlisted: ${resolvedRepo}` };
}

function isInsideOrSame(candidate: string, root: string): boolean {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}
```

- [x] **Step 4: Wire allowlist into workspace guard**

Modify `D:\GIT\deepcode-cli\src\lima\workspace-guard.ts`:

```ts
import { isRepoAllowed } from "./repo-allowlist";

export type LiMaWorkspaceGuardConfig = {
  currentWorkspace: string;
  allowedWorkspaceRoots?: string[];
  allowedRepos?: string[];
  maxRuntimeCapSec?: number;
};

export function resolveLiMaTaskRepo(repo: string, config: LiMaWorkspaceGuardConfig): LiMaWorkspaceGuardResult<string> {
  const requested = path.resolve(repo);
  if (!repo.trim()) {
    return { ok: false, error: "LiMa task repo is required." };
  }
  if (!fs.existsSync(requested)) {
    return { ok: false, error: `LiMa task repo does not exist: ${requested}` };
  }
  const allowed = isRepoAllowed(requested, {
    currentWorkspace: config.currentWorkspace,
    allowedRepos: [...(config.allowedWorkspaceRoots ?? []), ...(config.allowedRepos ?? [])],
  });
  if (!allowed.ok) {
    return allowed;
  }
  return { ok: true, value: requested };
}
```

- [x] **Step 5: Run allowlist tests**

Run:

```bash
npm.cmd test -- src/tests/lima-repo-allowlist.test.ts src/tests/lima-workspace-guard.test.ts
```

Expected: selected tests pass.

- [x] **Step 6: Commit Task 3**

```bash
git add src/lima/repo-allowlist.ts src/lima/workspace-guard.ts src/tests/lima-repo-allowlist.test.ts src/tests/lima-workspace-guard.test.ts
git commit -m "feat: require explicit lima repo allowlist"
```

---

## Task 4: Add Worker Session Budget

**Files:**

- Create: `D:\GIT\deepcode-cli\src\lima\worker-budget.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-worker-budget.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\command-runner.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`

- [x] **Step 1: Write failing budget tests**

Create `D:\GIT\deepcode-cli\src\tests\lima-worker-budget.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { createWorkerBudget } from "../lima/worker-budget";

test("worker budget allows work within limits", () => {
  const budget = createWorkerBudget({ maxTasks: 2, maxMinutes: 5, now: () => 0 });
  assert.equal(budget.canStartNext().ok, true);
  budget.recordTask();
  assert.equal(budget.canStartNext().ok, true);
});

test("worker budget stops at max tasks", () => {
  const budget = createWorkerBudget({ maxTasks: 1, maxMinutes: 5, now: () => 0 });
  budget.recordTask();
  const result = budget.canStartNext();
  assert.equal(result.ok, false);
  assert.match(result.reason, /task budget/);
});

test("worker budget stops at max minutes", () => {
  let now = 0;
  const budget = createWorkerBudget({ maxTasks: 10, maxMinutes: 1, now: () => now });
  now = 61_000;
  const result = budget.canStartNext();
  assert.equal(result.ok, false);
  assert.match(result.reason, /time budget/);
});
```

- [x] **Step 2: Implement budget helper**

Create `D:\GIT\deepcode-cli\src\lima\worker-budget.ts`:

```ts
export type LiMaWorkerBudgetConfig = {
  maxTasks: number;
  maxMinutes: number;
  now?: () => number;
};

export type LiMaWorkerBudgetDecision = { ok: true } | { ok: false; reason: string };

export function createWorkerBudget(config: LiMaWorkerBudgetConfig) {
  const startedAt = (config.now ?? Date.now)();
  const now = config.now ?? Date.now;
  let taskCount = 0;

  return {
    recordTask(): void {
      taskCount += 1;
    },
    canStartNext(): LiMaWorkerBudgetDecision {
      if (taskCount >= config.maxTasks) {
        return { ok: false, reason: `LiMa worker task budget reached: ${taskCount}/${config.maxTasks}` };
      }
      const elapsedMs = now() - startedAt;
      if (elapsedMs > config.maxMinutes * 60_000) {
        return { ok: false, reason: `LiMa worker time budget reached: ${config.maxMinutes} minute(s)` };
      }
      return { ok: true };
    },
  };
}
```

- [x] **Step 3: Wire budget into worker loop**

Modify `D:\GIT\deepcode-cli\src\lima\command-runner.ts`:

```ts
import { createWorkerBudget } from "./worker-budget";

const budget = createWorkerBudget({
  maxTasks: options.command.maxTasks,
  maxMinutes: options.command.maxMinutes ?? 60,
});

while (true) {
  const budgetDecision = budget.canStartNext();
  if (!budgetDecision.ok) {
    return { ok: true, message: budgetDecision.reason };
  }
  // existing fetch/run logic
  budget.recordTask();
}
```

- [x] **Step 4: Run budget tests**

Run:

```bash
npm.cmd test -- src/tests/lima-worker-budget.test.ts src/tests/lima-command-runner.test.ts
```

Expected: selected tests pass.

- [x] **Step 5: Commit Task 4**

```bash
git add src/lima/worker-budget.ts src/lima/command-runner.ts src/tests/lima-worker-budget.test.ts src/tests/lima-command-runner.test.ts
git commit -m "feat: add lima worker session budget"
```

---

## Task 5: Add Failure Quarantine

**Files:**

- Create: `D:\GIT\deepcode-cli\src\lima\failure-quarantine.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-failure-quarantine.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\command-runner.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\agent-task-client.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`
- Modify: `routes/agent_tasks.py`
- Modify: `tests/test_agent_task_routes.py`

- [ ] **Step 1: Write failing quarantine tests**

Create `D:\GIT\deepcode-cli\src\tests\lima-failure-quarantine.test.ts`:

```ts
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { recordTaskFailure, shouldQuarantineTask } from "../lima/failure-quarantine";

test("failure quarantine starts below threshold", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "lima-quarantine-"));
  recordTaskFailure(root, "task-1", "failed once");
  assert.equal(shouldQuarantineTask(root, "task-1", 3).quarantine, false);
});

test("failure quarantine triggers at threshold", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "lima-quarantine-"));
  recordTaskFailure(root, "task-1", "failed 1");
  recordTaskFailure(root, "task-1", "failed 2");
  recordTaskFailure(root, "task-1", "failed 3");
  const result = shouldQuarantineTask(root, "task-1", 3);
  assert.equal(result.quarantine, true);
  assert.equal(result.failureCount, 3);
});
```

- [ ] **Step 2: Implement quarantine helper**

Create `D:\GIT\deepcode-cli\src\lima\failure-quarantine.ts`:

```ts
import fs from "node:fs";
import path from "node:path";

type QuarantineRecord = {
  task_id: string;
  failure_count: number;
  last_error: string;
  updated_at: string;
};

type QuarantineState = Record<string, QuarantineRecord>;

export function recordTaskFailure(projectRoot: string, taskId: string, error: string): QuarantineRecord {
  const state = readState(projectRoot);
  const previous = state[taskId];
  const record: QuarantineRecord = {
    task_id: taskId,
    failure_count: (previous?.failure_count ?? 0) + 1,
    last_error: error,
    updated_at: new Date().toISOString(),
  };
  state[taskId] = record;
  writeState(projectRoot, state);
  return record;
}

export function shouldQuarantineTask(
  projectRoot: string,
  taskId: string,
  threshold = 3
): { quarantine: boolean; failureCount: number; reason: string } {
  const record = readState(projectRoot)[taskId];
  const failureCount = record?.failure_count ?? 0;
  return {
    quarantine: failureCount >= threshold,
    failureCount,
    reason: record?.last_error ?? "",
  };
}

function quarantinePath(projectRoot: string): string {
  return path.join(projectRoot, ".lima-code", "quarantine.json");
}

function readState(projectRoot: string): QuarantineState {
  const file = quarantinePath(projectRoot);
  if (!fs.existsSync(file)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(file, "utf8")) as QuarantineState;
}

function writeState(projectRoot: string, state: QuarantineState): void {
  const file = quarantinePath(projectRoot);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(state, null, 2), "utf8");
}
```

- [ ] **Step 3: Add Server quarantine endpoint**

Add to `routes/agent_tasks.py`:

```python
@router.post("/tasks/{task_id}/quarantine", dependencies=[Depends(_require_admin)])
async def quarantine_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    task = _tasks[task_id]
    task["status"] = "quarantined"
    task["updated_at"] = time.time()
    _append_event(task_id, {"type": "quarantined"})
    return {"task_id": task_id, "status": "quarantined"}
```

- [ ] **Step 4: Wire worker failure path**

Modify `D:\GIT\deepcode-cli\src\lima\command-runner.ts` so failed fetch/submit/task execution records a local failure. If threshold is reached, call `client.quarantineTask(task.task_id)` and stop the loop with a clear message:

```ts
const failure = recordTaskFailure(projectRoot, task.task_id, result.message);
const quarantine = shouldQuarantineTask(projectRoot, task.task_id, 3);
if (quarantine.quarantine && "quarantineTask" in client) {
  await client.quarantineTask(task.task_id);
  return {
    ok: false,
    message: `Task ${task.task_id} quarantined after ${failure.failure_count} failure(s): ${quarantine.reason}`,
  };
}
```

- [ ] **Step 5: Run quarantine tests**

Run:

```bash
npm.cmd test -- src/tests/lima-failure-quarantine.test.ts src/tests/lima-command-runner.test.ts
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py -q
```

Expected: selected tests pass.

- [ ] **Step 6: Commit Task 5**

Server:

```bash
git add routes/agent_tasks.py tests/test_agent_task_routes.py
git commit -m "feat: add agent task quarantine endpoint"
```

LiMa Code:

```bash
git add src/lima/failure-quarantine.ts src/lima/command-runner.ts src/lima/agent-task-client.ts src/tests/lima-failure-quarantine.test.ts src/tests/lima-command-runner.test.ts
git commit -m "feat: quarantine repeated lima worker failures"
```

---

## Task 6: Add Stop Marker and Worker Control Commands

**Files:**

- Create: `D:\GIT\deepcode-cli\src\lima\worker-control.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-worker-control.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\commands.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\command-runner.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-commands.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`

- [ ] **Step 1: Write failing command tests**

Add to `D:\GIT\deepcode-cli\src\tests\lima-commands.test.ts`:

```ts
test("parseLiMaCommand parses daemon lifecycle commands", () => {
  assert.deepEqual(parseLiMaCommand("/lima daemon status"), {
    ok: true,
    command: { kind: "daemon", action: "status" },
  });
  assert.deepEqual(parseLiMaCommand("/lima daemon stop"), {
    ok: true,
    command: { kind: "daemon", action: "stop" },
  });
});
```

- [ ] **Step 2: Implement stop marker helper**

Create `D:\GIT\deepcode-cli\src\lima\worker-control.ts`:

```ts
import fs from "node:fs";
import path from "node:path";

export function requestWorkerStop(projectRoot: string, reason = "user_requested"): string {
  const file = stopMarkerPath(projectRoot);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify({ reason, requested_at: new Date().toISOString() }, null, 2), "utf8");
  return file;
}

export function clearWorkerStop(projectRoot: string): void {
  const file = stopMarkerPath(projectRoot);
  if (fs.existsSync(file)) {
    fs.unlinkSync(file);
  }
}

export function readWorkerStop(projectRoot: string): { stop: boolean; reason: string } {
  const file = stopMarkerPath(projectRoot);
  if (!fs.existsSync(file)) {
    return { stop: false, reason: "" };
  }
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as { reason?: string };
    return { stop: true, reason: parsed.reason ?? "user_requested" };
  } catch {
    return { stop: true, reason: "unreadable_stop_marker" };
  }
}

function stopMarkerPath(projectRoot: string): string {
  return path.join(projectRoot, ".lima-code", "worker.stop.json");
}
```

- [ ] **Step 3: Parse daemon commands**

Modify `D:\GIT\deepcode-cli\src\lima\commands.ts`:

```ts
export type LiMaCommand =
  | { kind: "daemon"; action: "status" | "stop" }
  // existing command variants

if (subcommand === "daemon") {
  const action = parts[2] ?? "";
  if (action === "status" || action === "stop") {
    return { ok: true, command: { kind: "daemon", action } };
  }
  return { ok: false, error: "Usage: /lima daemon status | /lima daemon stop" };
}
```

- [ ] **Step 4: Check stop marker inside loop**

Modify `D:\GIT\deepcode-cli\src\lima\command-runner.ts`:

```ts
if (parsed.command.kind === "daemon") {
  if (parsed.command.action === "stop") {
    const marker = requestWorkerStop(options.projectRoot);
    return { ok: true, message: `LiMa worker stop requested: ${marker}` };
  }
  const stop = readWorkerStop(options.projectRoot);
  return { ok: true, message: stop.stop ? `LiMa worker stop pending: ${stop.reason}` : "LiMa worker stop is not pending." };
}

const stop = readWorkerStop(options.projectRoot);
if (stop.stop) {
  return { ok: true, message: `LiMa work stopped by marker: ${stop.reason}` };
}
```

- [ ] **Step 5: Run worker control tests**

Run:

```bash
npm.cmd test -- src/tests/lima-worker-control.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts
```

Expected: selected tests pass.

- [ ] **Step 6: Commit Task 6**

```bash
git add src/lima/worker-control.ts src/lima/commands.ts src/lima/command-runner.ts src/tests/lima-worker-control.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts
git commit -m "feat: add lima worker stop control"
```

---

## Task 7: Add Audit UI Commands

**Files:**

- Create: `D:\GIT\deepcode-cli\src\lima\audit-reader.ts`
- Create: `D:\GIT\deepcode-cli\src\tests\lima-audit-reader.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\commands.ts`
- Modify: `D:\GIT\deepcode-cli\src\lima\command-runner.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-commands.test.ts`
- Modify: `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`

- [ ] **Step 1: Write failing audit reader tests**

Create `D:\GIT\deepcode-cli\src\tests\lima-audit-reader.test.ts`:

```ts
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { formatAuditSummary, readRecentAuditEntries } from "../lima/audit-reader";

test("readRecentAuditEntries returns newest entries first", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "lima-audit-read-"));
  const dir = path.join(root, ".lima-code");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(
    path.join(dir, "audit.jsonl"),
    [
      JSON.stringify({ task_id: "old", status: "needs_review", created_at: "2026-05-23T00:00:00.000Z" }),
      JSON.stringify({ task_id: "new", status: "failed", created_at: "2026-05-23T00:01:00.000Z" }),
    ].join("\n") + "\n",
    "utf8",
  );

  const entries = readRecentAuditEntries(root, 1);
  assert.equal(entries.length, 1);
  assert.equal(entries[0]?.task_id, "new");
});

test("formatAuditSummary includes status and task id", () => {
  const text = formatAuditSummary([{ task_id: "task-1", status: "needs_review", mode: "review" }]);
  assert.match(text, /task-1/);
  assert.match(text, /needs_review/);
});
```

- [ ] **Step 2: Implement audit reader**

Create `D:\GIT\deepcode-cli\src\lima\audit-reader.ts`:

```ts
import fs from "node:fs";
import path from "node:path";

export type LiMaAuditSummaryEntry = {
  task_id?: string;
  status?: string;
  mode?: string;
  created_at?: string;
  repo?: string;
};

export function readRecentAuditEntries(projectRoot: string, limit = 10): LiMaAuditSummaryEntry[] {
  const file = path.join(projectRoot, ".lima-code", "audit.jsonl");
  if (!fs.existsSync(file)) {
    return [];
  }
  return fs.readFileSync(file, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => safeParse(line))
    .filter((entry): entry is LiMaAuditSummaryEntry => Boolean(entry))
    .sort((a, b) => String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")))
    .slice(0, limit);
}

export function formatAuditSummary(entries: LiMaAuditSummaryEntry[]): string {
  if (entries.length === 0) {
    return "No LiMa audit entries found.";
  }
  return entries
    .map((entry) => `${entry.created_at ?? "unknown"} ${entry.task_id ?? "unknown"} ${entry.status ?? "unknown"} ${entry.mode ?? ""}`.trim())
    .join("\n");
}

function safeParse(line: string): LiMaAuditSummaryEntry | null {
  try {
    return JSON.parse(line) as LiMaAuditSummaryEntry;
  } catch {
    return null;
  }
}
```

- [ ] **Step 3: Add `/lima audit` command**

Modify `D:\GIT\deepcode-cli\src\lima\commands.ts`:

```ts
| { kind: "audit"; limit: number }

if (subcommand === "audit") {
  const limit = readPositiveInt(parts.slice(2), "--last", 10);
  if (!limit.ok) {
    return limit;
  }
  return { ok: true, command: { kind: "audit", limit: limit.value } };
}
```

Modify `D:\GIT\deepcode-cli\src\lima\command-runner.ts`:

```ts
if (parsed.command.kind === "audit") {
  return {
    ok: true,
    message: formatAuditSummary(readRecentAuditEntries(options.projectRoot, parsed.command.limit)),
  };
}
```

- [ ] **Step 4: Run audit tests**

Run:

```bash
npm.cmd test -- src/tests/lima-audit-reader.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts
```

Expected: selected tests pass.

- [ ] **Step 5: Commit Task 7**

```bash
git add src/lima/audit-reader.ts src/lima/commands.ts src/lima/command-runner.ts src/tests/lima-audit-reader.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts
git commit -m "feat: add lima audit command"
```

---

## Task 8: Real Repository Smoke Path

**Files:**

- Modify: `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`
- Modify: `D:\GIT\deepcode-cli\docs\lima-mcp-worker-plan.md`
- Modify: `progress.md`
- Modify: `docs/LIMA_MEMORY.md`

- [ ] **Step 1: Add temp git repo smoke test**

Add to `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`:

```ts
test("executeLiMaCommand can patch and test a temporary real repo", async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "lima-real-repo-"));
  fs.writeFileSync(path.join(repo, "package.json"), JSON.stringify({ scripts: { test: "node test.js" } }), "utf8");
  fs.writeFileSync(path.join(repo, "test.js"), "console.log('ok')\n", "utf8");

  const task: LiMaTaskRunnerRequest = {
    task_id: "real-repo",
    repo,
    branch: "main",
    goal: "touch file and run tests",
    constraints: [],
    allowed_tools: ["write", "git_diff", "test"],
    max_runtime_sec: 30,
    mode: "patch",
    patch_files: [{ path: "README.md", content: "# Smoke\n" }],
    test_commands: ["npm test"],
  };

  const submitted: LiMaAgentTaskResult[] = [];
  const response = await executeLiMaCommand("/lima task real-repo", {
    projectRoot: repo,
    client: {
      isConfigured: () => true,
      fetchTask: async () => ({ ok: true, value: task }),
      fetchPendingTask: async () => ({ ok: true, value: null }),
      submitResult: async (result) => {
        submitted.push(result);
        return { ok: true, value: { accepted: true } };
      },
      fetchTaskEvents: async () => ({ ok: true, value: [] }),
    },
  });

  assert.equal(response.ok, true);
  assert.equal(submitted.length, 1);
  assert.deepEqual(submitted[0]?.changed_files, ["README.md"]);
});
```

- [ ] **Step 2: Run real repo smoke test**

Run:

```bash
npm.cmd test -- src/tests/lima-command-runner.test.ts
```

Expected: command runner tests pass and the temp repo smoke submits one result.

- [ ] **Step 3: Perform public safe smoke**

Use a temporary repo, never a private working repo with unreviewed code. Create a Server task with:

```json
{
  "repo": "<temporary repo path>",
  "branch": "main",
  "goal": "Add README smoke file and run tests",
  "constraints": ["Do not modify files outside the repo", "Return needs_review"],
  "allowed_tools": ["write", "git_diff", "test"],
  "max_runtime_sec": 60,
  "mode": "patch"
}
```

Run LiMa Code:

```bash
/lima task <task_id>
```

Expected Server evidence:

```text
status=needs_review
events=created,claimed,result_submitted
changed_files includes README.md
test_results includes one passing command
```

- [ ] **Step 4: Update docs with smoke evidence**

Append exact evidence to:

- `progress.md`
- `docs/LIMA_MEMORY.md`
- `D:\GIT\deepcode-cli\docs\lima-mcp-worker-plan.md`

- [ ] **Step 5: Commit Task 8**

LiMa Code:

```bash
git add src/tests/lima-command-runner.test.ts docs/lima-mcp-worker-plan.md
git commit -m "test: cover real repo lima worker smoke"
```

Server docs:

```bash
git add progress.md docs/LIMA_MEMORY.md
git commit -m "docs: record autonomous worker v0.2 smoke"
```

---

## Task 9: Full Verification and Documentation Closure

**Files:**

- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `progress.md`
- Modify: `D:\GIT\deepcode-cli\docs\lima-mcp-worker-plan.md`

- [ ] **Step 1: Run Server focused lifecycle tests**

Run:

```bash
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_contract.py tests\test_agent_task_routes.py tests\test_agent_evolution.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run LiMa Code lifecycle tests**

Run:

```bash
npm.cmd test -- src/tests/lima-agent-task-types.test.ts src/tests/lima-agent-task-client.test.ts src/tests/lima-repo-allowlist.test.ts src/tests/lima-worker-budget.test.ts src/tests/lima-failure-quarantine.test.ts src/tests/lima-worker-control.test.ts src/tests/lima-audit-reader.test.ts src/tests/lima-commands.test.ts src/tests/lima-command-runner.test.ts
```

Expected: all selected tests pass.

- [ ] **Step 3: Run LiMa Code full checks**

Run:

```bash
npm.cmd run check
npm.cmd test
```

Expected: check passes and full suite has zero failures.

- [ ] **Step 4: Update status docs**

Update `STATUS.md`:

```markdown
| LiMa Code worker lifecycle | Designed/Implemented | v0.2 adds stop control, repo allowlist, worker budget, failure quarantine, audit command, and real-repo smoke path. |
```

Append to `docs/LIMA_MEMORY.md`:

```markdown
## 2026-05-23 LiMa Autonomous Worker v0.2

LiMa follows the GenericAgent/Evolver/agency-agents direction through controlled autonomy:

- GenericAgent-like skill growth becomes inactive candidate skills, not self-published runtime behavior.
- Evolver-like evolution becomes evidence-gated promotion with tests and manual approval.
- agency-agents-like roles remain a compact coding role set, not a large simulated company.
- Server orchestrates and audits; LiMa Code executes locally inside allowlisted repos.
- v0.2 lifecycle controls are stop markers, claim leases, cancellation, runtime budgets, failure quarantine, and audit viewing.
```

Append to `progress.md`:

```markdown
## 2026-05-23 LiMa Autonomous Worker v0.2

- Implemented lifecycle contract and Server claim/cancel/control/review/quarantine endpoints.
- Implemented LiMa Code repo allowlist, worker budget, failure quarantine, stop control, and audit command.
- Verified with focused Server tests, focused LiMa Code tests, full LiMa Code check, full LiMa Code suite, and safe real-repo smoke.
```

- [ ] **Step 5: Commit documentation closure**

Server:

```bash
git add STATUS.md docs/LIMA_MEMORY.md progress.md
git commit -m "docs: close autonomous worker v0.2 lifecycle"
```

LiMa Code:

```bash
git add docs/lima-mcp-worker-plan.md
git commit -m "docs: record autonomous worker lifecycle controls"
```

- [ ] **Step 6: Push both repositories**

Run:

```bash
git push origin codex/free-web-ai-probe
```

Then in `D:\GIT\deepcode-cli`:

```bash
git push origin main
```

Expected: both pushes succeed.

---

## Acceptance Criteria

LiMa v0.2 is complete only when all of these are true:

- Server can claim a task with `worker_id` and lease metadata.
- Server can request cancellation, and LiMa Code can observe stop/cancel controls.
- LiMa Code refuses to touch non-allowlisted repositories.
- LiMa Code stops when worker-session budget is reached.
- LiMa Code quarantines repeated failures and reports that status to Server.
- LiMa Code exposes a user-facing audit summary command.
- A safe temp real-repo smoke proves patch plus test plus result submission.
- Evolution remains candidate-only until tests and manual promotion pass.
- Documentation records the exact evidence.

## Risk Controls

- Do not run a public smoke against `D:\GIT` or another large private repo unless the task is read-only.
- Do not send full private diffs to Server unless the user explicitly approved that repo and task.
- Do not allow Server to execute shell.
- Do not add auto-commit, auto-push, or auto-deploy in v0.2.
- Do not promote candidate skills without test evidence and manual flag.
- Do not store credentials in audit files; keep current redaction behavior.

## Future v0.3 Candidates

- Background OS service wrapper.
- Web admin audit UI.
- Worker heartbeat dashboard.
- Multi-worker scheduling.
- Role-specific task queues.
- Regression-suite-driven skill promotion.
- Per-repo trust levels and signed task policies.
