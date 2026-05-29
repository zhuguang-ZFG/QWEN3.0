# LiMa Code OpenCode-Style Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` only after the dry-run design tasks are complete. Use `safety-guard` before any autonomous runner, shell execution, MCP connector, VPS deployment, or GitHub/Gitee write action. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the OpenCode / oh-my-opencode lesson into a LiMa-native, default-off multi-role coding workflow for LiMa Code without replacing LiMa's router, safety gates, or milestone closeout protocol.

**Architecture:** LiMa keeps provider/key custody, backend routing, memory, review, tests, and deployment evidence. LiMa Code gains a small orchestration layer that can plan roles, assign allowed tools, choose model tiers, and emit an execution manifest before any code changes. The first usable slice is dry-run only; later slices add controlled role execution, diagnostics, review, and evidence capture.

**Tech Stack:** LiMa Server Python/FastAPI, LiMa Code `deepcode-cli` TypeScript/Node, repo `AGENTS.md`, existing docs/reference ledgers, pytest/npm test suites, optional MCP connectors from `docs/reference/MCP_CONNECTOR_CATALOG.md`.

---

## Source References

| Reference | Status In LiMa | Borrow | Do Not Borrow |
|---|---|---|---|
| OpenCode | Already tracked in `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md` and `docs/LIMACODE_MANAGEMENT.md` | Plan/Build separation, terminal workflow ergonomics, provider-agnostic coding agent posture | Do not replace LiMa routing, backend admission, or closeout gates |
| oh-my-opencode | New concept reference from user-provided article and public docs | Role teams, hooks, LSP/diagnostic loop, MCP/context integration, command shortcuts | Do not install broad external role packs by default; do not run hidden write-capable agents |
| AgentConductor / existing multi-agent notes | Already tracked | Dynamic topology: simple tasks stay single-agent, hard tasks expand roles | Do not add agents for spectacle or without budget/eval evidence |
| `AGENTS.md` | Active project rule source | Project-specific operating constraints and milestone protocol | Do not bury production safety rules inside tool-specific prompts only |

## Product Filter

This plan is useful only if it improves real LiMa productivity:

- faster unfamiliar-code onboarding;
- safer broad refactors;
- better coding review/test/deploy closeout;
- stronger LiMa Code worker UX;
- clearer role/tool/model boundaries;
- lower wasted tokens through dynamic role selection.

It is not a plan to clone OpenCode, add a decorative "AI team" UI, or bypass the current owner/agent milestone protocol.

## Role Model

| LiMa Role | Inspired By | Responsibility | Default Tools | Write Access |
|---|---|---|---|---|
| `planner` | Sisyphus / Plan mode | Classify task, choose topology, write execution manifest | repo docs, `rg`, git status, task history | No |
| `explorer` | Explore | Gather code facts, dependency paths, file owners, existing tests | `rg`, read-only shell, docs | No |
| `librarian` | Librarian | Fetch official docs and external references, record citations | Context7, Microsoft Learn, web search, reference docs | No |
| `architect` | Oracle | Decide boundaries, risk, interfaces, migration path | docs, source reads, prior findings | No |
| `implementer` | Hephaestus / Build mode | Make scoped code changes after manifest approval | filesystem/code edit tools, focused tests | Yes, scoped |
| `verifier` | LSP/diagnostics loop | Run diagnostics, tests, smoke, secret scans, `git diff --check` | test runners, linters, smoke scripts | No code writes unless fixing test harness by approval |
| `reviewer` | Momus | Review diff for bugs, regressions, safety, missing tests | git diff, tests, security checklist | No |
| `operator` | Closeout owner | Update docs/findings/progress, stage only related files, commit/push if requested | git, docs, VPS smoke only when approved by project rules | Scoped, explicit |

## Topology Rules

| Task Type | Default Topology | Escalate When | Budget Boundary |
|---|---|---|---|
| Simple bug or doc edit | `planner -> implementer -> verifier` | touches production routing, auth, deployment, or hardware | one implementation pass |
| Unfamiliar module | `planner + explorer -> architect -> implementer -> verifier -> reviewer` | explorer finds cross-module impact | read-only phase first |
| Broad refactor | `planner + explorer + librarian -> architect -> implementer slices -> verifier -> reviewer` | more than 3 modules or data/schema change | split into milestone slices |
| External resource adoption | `planner + librarian -> architect -> dry-run artifact -> verifier` | new network/cloud/MCP/provider behavior | default-off, report-only |
| ESP32 / Device Gateway | `planner + explorer + architect -> fake-device verifier -> implementer -> hardware/operator smoke` | hardware write, OTA, public route, device token | fake first, real device explicit |
| Production/VPS | `planner -> operator -> verifier` | deploy, restart, tunnel, secret, database, public route | backup, smoke, rollback note |

## Execution Manifest

Every multi-role run must produce a manifest before code writes:

```json
{
  "schema_version": "lima.orchestration.v0",
  "task_id": "manual-YYYYMMDD-slug",
  "mode": "dry_run",
  "topology": ["planner", "explorer", "architect", "implementer", "verifier", "reviewer"],
  "scope": {
    "repos": ["D:/GIT", "D:/GIT/deepcode-cli"],
    "allowed_paths": ["docs/", "tests/", "specific/module.py"],
    "blocked_paths": [".env", "data/private", "reference repos", "generated caches"]
  },
  "models": {
    "planner": "cheap_reasoning",
    "explorer": "fast_context",
    "architect": "strong_reasoning",
    "implementer": "coding",
    "verifier": "cheap_deterministic",
    "reviewer": "strong_review"
  },
  "tools": {
    "read_only": ["rg", "git diff", "docs search"],
    "write": ["scoped code edit"],
    "network": "off_by_default",
    "vps": "off_by_default"
  },
  "required_evidence": ["focused_tests", "git_diff_check", "docs_update"],
  "rollback": "describe before enabling write mode"
}
```

## Milestones

### Milestone 0: Reference Admission And Boundary Update

**Files:**
- Modify: `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`
- Modify: `docs/LIMACODE_MANAGEMENT.md`
- Modify: `docs/DOCUMENTATION_STATUS.md`
- Optional modify: `docs/REFERENCE_IMPLEMENTATION_LEDGER.md`

- [ ] **Step 1: Add oh-my-opencode as a concept/reference entry**

  Add a row near the OpenCode / oh-my-codex / subagent references:

  ```markdown
  | `oh-my-opencode` | OpenCode extension ecosystem for agents, hooks, MCP/context, diagnostics, and role-based workflows. | License/source must be reviewed before code reuse | Borrow role-team orchestration, hook/diagnostic loop, and command ergonomics for LiMa Code; do not install broad role packs or run write-capable external agents by default. | LiMa Code |
  ```

- [ ] **Step 2: Add LiMa Code management boundary**

  Add a short bullet in `docs/LIMACODE_MANAGEMENT.md`:

  ```markdown
  - `oh-my-opencode`: concept/reference for OpenCode-style agent teams,
    hooks, MCP/context loading, and diagnostics. LiMa Code may borrow the
    orchestration shape, but role definitions, model routing, tool permissions,
    budget telemetry, and closeout evidence remain LiMa-owned.
  ```

- [ ] **Step 3: Link this implementation plan from documentation status**

  Add this plan as an active/deferred plan, depending on current milestone load:

  ```markdown
  | `docs/superpowers/plans/2026-05-26-lima-code-opencode-orchestration.md` | Deferred plan | OpenCode/oh-my-opencode-inspired LiMa Code role orchestration; dry-run first, default-off, no runtime dependency adoption. |
  ```

- [ ] **Step 4: Verify docs formatting**

  Run:

  ```powershell
  git diff --check -- docs\reference\EXTERNAL_CAPABILITY_RADAR_2026-05-24.md docs\LIMACODE_MANAGEMENT.md docs\DOCUMENTATION_STATUS.md docs\superpowers\plans\2026-05-26-lima-code-opencode-orchestration.md
  ```

  Expected: no whitespace errors. CRLF warnings are acceptable if already present.

### Milestone 1: Dry-Run Orchestration Manifest

**Files:**
- Create: `docs/LIMACODE_ORCHESTRATION_MANIFEST.md`
- Create later only after design approval: `deepcode-cli/src/orchestration/manifest.ts`
- Create later only after design approval: `deepcode-cli/src/orchestration/roles.ts`
- Test later only after design approval: `deepcode-cli/src/orchestration/manifest.test.ts`

- [ ] **Step 1: Document the manifest schema before code**

  Create `docs/LIMACODE_ORCHESTRATION_MANIFEST.md` with:

  ```markdown
  # LiMa Code Orchestration Manifest

  The manifest is a dry-run artifact that describes role topology, allowed
  paths, tools, model class, evidence, and rollback before any multi-agent run.

  Required fields:
  - `schema_version`
  - `task_id`
  - `mode`
  - `topology`
  - `scope.repos`
  - `scope.allowed_paths`
  - `scope.blocked_paths`
  - `models`
  - `tools`
  - `required_evidence`
  - `rollback`

  Modes:
  - `dry_run`: writes only the manifest.
  - `read_only`: agents may inspect code/docs but not edit.
  - `scoped_write`: implementer may edit only approved paths.
  - `closeout`: verifier/reviewer/operator evidence collection.
  ```

- [ ] **Step 2: Add a TypeScript manifest type**

  Implement only after the document is reviewed:

  ```ts
  export type OrchestrationMode = "dry_run" | "read_only" | "scoped_write" | "closeout";

  export interface OrchestrationManifest {
    schema_version: "lima.orchestration.v0";
    task_id: string;
    mode: OrchestrationMode;
    topology: string[];
    scope: {
      repos: string[];
      allowed_paths: string[];
      blocked_paths: string[];
    };
    models: Record<string, string>;
    tools: {
      read_only: string[];
      write: string[];
      network: "off_by_default" | "allowlisted";
      vps: "off_by_default" | "allowlisted";
    };
    required_evidence: string[];
    rollback: string;
  }
  ```

- [ ] **Step 3: Test manifest validation**

  Add tests that reject:

  ```ts
  {
    schema_version: "lima.orchestration.v0",
    task_id: "manual-test",
    mode: "scoped_write",
    topology: ["implementer"],
    scope: { repos: ["D:/GIT"], allowed_paths: [], blocked_paths: [".env"] },
    models: {},
    tools: { read_only: [], write: ["scoped code edit"], network: "allowlisted", vps: "allowlisted" },
    required_evidence: [],
    rollback: ""
  }
  ```

  Expected rejection reasons:
  - write mode cannot have empty `allowed_paths`;
  - network/VPS allowlist requires explicit policy;
  - rollback cannot be empty.

### Milestone 2: Role Registry And Permission Classes

**Files:**
- Create later: `deepcode-cli/src/orchestration/roles.ts`
- Create later: `deepcode-cli/src/orchestration/permissions.ts`
- Test later: `deepcode-cli/src/orchestration/roles.test.ts`

- [ ] **Step 1: Define role metadata**

  Role metadata must include:

  ```ts
  export interface RoleDefinition {
    id: "planner" | "explorer" | "librarian" | "architect" | "implementer" | "verifier" | "reviewer" | "operator";
    purpose: string;
    defaultPermission: "read_only" | "scoped_write" | "closeout";
    defaultModelClass: "cheap_reasoning" | "fast_context" | "strong_reasoning" | "coding" | "cheap_deterministic" | "strong_review";
    allowedTools: string[];
    blockedActions: string[];
  }
  ```

- [ ] **Step 2: Encode hard safety boundaries**

  Permissions must reject:

  - arbitrary shell in `dry_run`;
  - code writes outside `allowed_paths`;
  - `.env`, credentials, local DB, caches, and reference repos unless explicitly allowlisted;
  - production/VPS actions unless mode is `closeout` and rollback evidence exists;
  - MCP connector use unless connector appears in `docs/reference/MCP_CONNECTOR_CATALOG.md` and is enabled by explicit config.

- [ ] **Step 3: Verify role registry**

  Tests must assert:

  - `planner`, `explorer`, `librarian`, `architect`, `reviewer`, and `verifier` are read-only by default;
  - only `implementer` can request scoped writes;
  - `operator` cannot edit code by default;
  - every role has at least one blocked action.

### Milestone 3: Task Classifier And Dynamic Topology

**Files:**
- Create later: `deepcode-cli/src/orchestration/topology.ts`
- Test later: `deepcode-cli/src/orchestration/topology.test.ts`
- Docs: update `docs/LIMACODE_ORCHESTRATION_MANIFEST.md`

- [ ] **Step 1: Implement simple deterministic classifier**

  Initial classifier rules:

  ```text
  docs_only -> planner, implementer, verifier
  single_file_bug -> planner, implementer, verifier, reviewer
  unknown_codebase -> planner, explorer, architect, verifier
  broad_refactor -> planner, explorer, librarian, architect, implementer, verifier, reviewer
  external_resource -> planner, librarian, architect, verifier
  esp32_or_device -> planner, explorer, architect, implementer, verifier, reviewer
  production_or_vps -> planner, operator, verifier, reviewer
  ```

- [ ] **Step 2: Keep simple tasks simple**

  Add a guard:

  ```ts
  if (input.files.length <= 1 && !input.touchesProduction && !input.touchesHardware) {
    return ["planner", "implementer", "verifier"];
  }
  ```

  This prevents token waste from spawning a full team for tiny work.

- [ ] **Step 3: Require reason strings**

  Every topology decision must return:

  ```ts
  {
    roles: ["planner", "explorer", "architect"],
    reason: "Touches unknown module and has no focused test path yet.",
    budgetClass: "medium"
  }
  ```

### Milestone 4: Dry-Run CLI Command

**Files:**
- Modify later: `deepcode-cli` CLI command registration file after inspecting current structure
- Create later: `deepcode-cli/src/orchestration/commands.ts`
- Test later: command/unit test matching current test framework

- [ ] **Step 1: Add default-off command**

  Command shape:

  ```text
  lima-code orchestrate --dry-run "refactor provider inventory validation"
  ```

  Output:

  ```text
  mode: dry_run
  topology: planner -> explorer -> architect -> implementer -> verifier -> reviewer
  writes: disabled
  network: disabled
  vps: disabled
  manifest: artifacts/orchestration/manual-YYYYMMDD-refactor-provider-inventory-validation.json
  ```

- [ ] **Step 2: Never edit code in dry-run**

  Tests must assert command creates only:

  - manifest artifact;
  - optional console output;
  - no source file changes.

- [ ] **Step 3: Add evidence capture**

  Manifest should include:

  - current branch;
  - dirty worktree summary;
  - relevant docs consulted;
  - blocked paths;
  - planned tests.

### Milestone 5: Read-Only Role Execution

**Files:**
- Create later: `deepcode-cli/src/orchestration/readOnlyRunner.ts`
- Test later: `deepcode-cli/src/orchestration/readOnlyRunner.test.ts`

- [ ] **Step 1: Implement read-only explorer run**

  Explorer can run only:

  ```text
  rg
  git status --short
  git diff --name-only
  read known docs
  ```

- [ ] **Step 2: Implement librarian run**

  Librarian can use:

  - official docs search;
  - Context7 docs;
  - existing `docs/reference/*` records.

  It must record source links and date.

- [ ] **Step 3: Store read-only findings**

  Output artifact:

  ```json
  {
    "task_id": "manual-YYYYMMDD-slug",
    "role": "explorer",
    "facts": [
      {
        "file": "D:/GIT/example.py",
        "line": 12,
        "claim": "Function X owns provider admission."
      }
    ],
    "unknowns": [],
    "recommended_next_roles": ["architect"]
  }
  ```

### Milestone 6: Scoped Write Execution

**Files:**
- Create later only after Milestones 1-5 are stable: `deepcode-cli/src/orchestration/scopedWriteRunner.ts`
- Tests later: scoped write safety tests

- [ ] **Step 1: Require manifest approval**

  `scoped_write` mode must fail unless:

  - manifest exists;
  - `allowed_paths` is non-empty;
  - `blocked_paths` includes secrets/local data patterns;
  - focused tests are named;
  - rollback note is non-empty.

- [ ] **Step 2: Execute one implementer at a time**

  Even if planning uses multiple roles, only one write-capable implementer runs at once. Parallelism is allowed for read-only research, not simultaneous edits.

- [ ] **Step 3: Run verifier immediately after write**

  Required commands:

  ```powershell
  git diff --check
  pytest <focused tests>
  ```

  Add npm/TypeScript tests when files under `deepcode-cli` change.

### Milestone 7: Review And Closeout Loop

**Files:**
- Update later: `docs/LIMACODE_MANAGEMENT.md`
- Update later: `progress.md`
- Update later: `findings.md`

- [ ] **Step 1: Reviewer summarizes risks first**

  Review output order:

  1. findings by severity;
  2. missing tests;
  3. residual risk;
  4. change summary.

- [ ] **Step 2: Operator updates durable records**

  For milestone closeout, update:

  - `progress.md`;
  - `findings.md`;
  - affected design/runbook docs;
  - `STATUS.md` / `docs/LIMA_MEMORY.md` only when runtime facts change.

- [ ] **Step 3: Stage only related files**

  Never stage:

  - `.claude/`;
  - local reference repos;
  - temporary debug scripts;
  - databases;
  - credentials;
  - generated caches.

## Verification Matrix

| Change Type | Required Verification |
|---|---|
| Docs-only plan/reference update | `git diff --check -- <docs>` |
| LiMa Code orchestration TS | package test/lint/build commands from `deepcode-cli/package.json` |
| Python Server integration | focused pytest, then full pytest before closeout |
| MCP connector enablement | catalog entry, default-off config, least-privilege review, local smoke |
| VPS/production action | backup, deploy/restart, health, public smoke, rollback note |
| ESP32/hardware | fake-device/schema tests first, compile where available, real-device explicit |

## Risks And Controls

| Risk | Control |
|---|---|
| Token blow-up from too many roles | Dynamic topology and budget class; simple tasks stay single-agent |
| Hidden write-capable agents | Manifest approval, allowed paths, one implementer at a time |
| External role pack prompt injection | Treat external role definitions as references, not runtime prompts |
| Tool/MCP over-permission | Connector catalog allowlist and default-off config |
| Production accident | No VPS action outside closeout/operator mode with rollback note |
| Review theater | Reviewer must cite files/tests and lead with concrete findings |
| Duplicating LiMa router | Models are classes mapped by LiMa; provider/key custody stays in LiMa |

## First Practical Slice

The recommended first implementation slice is intentionally small:

1. update reference docs with oh-my-opencode boundary;
2. write `docs/LIMACODE_ORCHESTRATION_MANIFEST.md`;
3. add a dry-run manifest generator only;
4. prove dry-run produces no code changes;
5. run formatting/tests for the changed package;
6. update progress/findings with evidence.

Do not implement autonomous parallel coding until the dry-run manifest, role registry, and read-only runner have fresh test evidence.
