# LiMa Vibe Coding Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `safety-guard` for this work. Use `superpowers:verification-before-completion` before marking any phase done. Use `superpowers:subagent-driven-development` only after the local fork is cloned and understood.
>
> **Current policy:** The fork is being rebranded as **LiMa**. User-facing product names should say LiMa / `lima`. The old `.deepcode` config path and `DEEPCODE_*` environment variables remain as a legacy compatibility layer until a tested migration is added.

**Goal:** Turn the user's fork `zhuguang-ZFG/deepcode-cli` into **LiMa**, a LiMa-powered vibe coding worker: LiMa provides the user-facing coding workflow, CLI/Web experience, and multi-agent project execution; LiMa provides OpenAI-compatible model routing, memory, safety, mastery profile, and final verification gates.

**Fork:**

- `https://github.com/zhuguang-ZFG/deepcode-cli.git`

**Target local path:**

- `D:\GIT\deepcode-cli`

---

## Strategic Decision

Use LiMa as the first-class vibe coding shell, not as a hidden worker behind LiMa.

```text
User
  -> LiMa CLI / Web UI / future voice/mobile entry
  -> LiMa coding workflow
  -> LiMa OpenAI-compatible endpoint
  -> LiMa routes model calls, records memory, and runs safety/verification logic
```

This is faster than rebuilding a coding UI inside LiMa. It also keeps LiMa focused on what it already does well: routing, memory, backend scoring, access guard, evidence capture, and VPS discipline.

---

## Non-Goals

- Do not merge LiMa into the LiMa repo.
- Do not let LiMa write directly to production LiMa files during initial tests.
- Do not deploy LiMa to VPS in the first pass.
- Do not give LiMa unrestricted shell, token files, `.env`, or deployment credentials.
- Do not allow automatic `git push`, VPS deployment, nginx/firewall edits, or destructive commands.
- Do not copy upstream code into LiMa; keep it in the forked repository.

---

## Phase 0: Clone And Baseline Inventory

**Steps:**

- [x] Clone the fork to `D:\GIT\deepcode-cli`.
- [x] Identify package manager and runtime: TypeScript CLI on npm, upstream package `@vegamo/deepcode-cli`, Node `>=22`.
- [x] Read key docs: README, AGENTS, configuration docs, CLI/provider references.
- [x] Identify where OpenAI-compatible provider base URL and model name are configured: `~/.deepcode/settings.json`, project `.deepcode/settings.json`, or `DEEPCODE_*` environment variables.
- [x] Identify where workspace path, task directory, and generated outputs are stored: CLI uses current project root plus session state; no LiMa-specific adapter yet.
- [x] Identify any default tool permissions or shell execution paths: built-in `bash`, `read`, `write`, `edit`, `AskUserQuestion`, `UpdatePlan`, and `WebSearch`; `bash` executes real local shell commands.
- [x] Record findings in `findings.md` and `progress.md`.

**Exit criteria:**

- The fork exists locally.
- We know how to run it locally.
- We know the minimal provider config needed to point it at LiMa.

Status: complete for inventory, dependency install, and baseline checks. Runtime sandbox execution is still pending a LiMa provider key/profile.

---

## Phase 1: LiMa Provider Configuration

**Purpose:** Make LiMa call LiMa as an OpenAI-compatible provider.

### Phase 1A: LiMa-Native Config Compatibility

**Purpose:** Make LiMa feel like its own product without breaking the upstream-compatible install base.

**Decision:**

- Prefer `~/.lima/settings.json` over `~/.deepcode/settings.json`.
- Prefer `<project>/.lima/settings.json` over `<project>/.deepcode/settings.json`.
- Prefer `LIMA_*` environment variables over legacy `DEEPCODE_*` variables with the same stripped key.
- Continue reading `.deepcode` and `DEEPCODE_*` as a compatibility fallback.
- Write new user/project settings to `.lima` by default.
- If a project already has only `.deepcode/settings.json`, model-selection writes should update that existing legacy project file instead of silently creating a second project config.

**Required tests:**

- Settings source resolution proves `LIMA_MODEL` wins over `DEEPCODE_MODEL`.
- MCP env merge proves `LIMA_MCP_*` wins over `DEEPCODE_MCP_*`.
- User settings read prefers `.lima` and falls back to `.deepcode`.
- Project settings read prefers `.lima` and falls back to `.deepcode`.
- Settings writes create `.lima/settings.json`.
- Model-selection writes update an existing legacy project settings file when no `.lima` project config exists.

**Status:** Complete in the local fork. Verified by `npm.cmd run test:single -- src/tests/settings-and-notify.test.ts src/tests/app-settings-paths.test.ts src/tests/web-search-handler.test.ts`.

**Expected config shape:**

```text
base_url: https://chat.donglicao.com/v1
api_key: lima-local or owner-provided private key
model: lima-1.3
```

**Safer local option:**

```text
base_url: http://127.0.0.1:8080/v1
api_key: local dev key from ignored env/config
model: lima-1.3
```

**Rules:**

- Store keys only in ignored local config or environment variables.
- Do not commit keys.
- Do not paste keys into docs or logs.
- Prefer a LiMa config profile named `lima`.

**Tests/checks:**

- LiMa can list or call a trivial model through LiMa.
- LiMa receives the request as OpenAI-compatible traffic.
- No secret is committed.

---

## Phase 2: Safe Vibe Coding Sandbox

**Purpose:** Prove the workflow on a disposable repository before pointing it at `D:\GIT`.

**Create or use later:**

```text
D:\GIT\lima-sandbox\
```

**Rules:**

- No production repo as first target.
- No deployment scripts.
- No credentials.
- No `git push`.
- Task must be tiny: add a function, add a test, fix a toy bug.

**Evidence to collect:**

- LiMa plan.
- Files touched.
- Diff.
- Commands run.
- Test output.
- Failure modes.

**Exit criteria:**

- LiMa can complete a tiny task using LiMa as model provider.
- Output can be reviewed before merge.

---

## Phase 3: LiMa Safety Profile For LiMa

**Purpose:** Restrict LiMa before using it on real projects.

**Required boundaries:**

- Deny `.env`, credential files, private token logs, and deployment secrets.
- Deny destructive commands by default.
- Deny direct VPS, nginx, firewall, service restart, and SSH operations.
- Require explicit owner approval for GitHub push/PR.
- Force generated patch and summary before any file landing in protected repos.

**Possible implementation points after inventory:**

- LiMa provider config.
- LiMa tool permission config.
- Wrapper script around LiMa CLI.
- LiMa Tool Gateway policy if LiMa calls LiMa tools.
- Repo-level AGENTS.md inside sandbox/worktree.

**Exit criteria:**

- Running LiMa on a protected repo cannot read obvious secret files or run disallowed commands.

---

## Phase 4: LiMa Result Adapter For LiMa Memory

**Purpose:** Feed LiMa task results back into LiMa.

**Output contract:**

```json
{
  "task": "...",
  "repo": "...",
  "plan": "...",
  "touched_files": [],
  "diff_summary": "...",
  "commands": [],
  "test_result": "...",
  "risk_summary": "...",
  "status": "success|failed|blocked"
}
```

**LiMa destinations later:**

- `session_memory`
- `mastery_loop`
- `agent_workbench`
- `findings.md` / `progress.md` for human-readable audit

**Exit criteria:**

- A LiMa run can be summarized into a LiMa memory/mastery event without raw secrets.

---

## Phase 5: Real LiMa Repo Trial In Worktree Only

**Purpose:** Test against real LiMa code without touching the dirty main workspace.

**Rules:**

- Use a git worktree or copied sandbox, not the current dirty `D:\GIT` root.
- Pick a low-risk doc-only or test-only task first.
- Require local verification.
- No deploy.
- No push unless owner approves.

**Exit criteria:**

- LiMa + LiMa can produce a reviewable patch on a real LiMa task.
- The patch includes plan, diff, tests, and risk summary.

---

## Phase 6: Vibe Coding UX Layer

**Purpose:** Make it feel good to use after safety and baseline work.

**Potential additions:**

- `lima` profile command.
- Windows `.bat` launcher.
- Local notification on completion.
- Optional `lima-local-agent` TTS/desktop notification.
- Future mobile/voice entry.

**Exit criteria:**

- Owner can start a LiMa + LiMa coding task with one command and get a clear completion signal.

---

## Verification Gate

Before claiming any implementation slice complete:

```powershell
git -C D:\GIT diff --check
git -C D:\GIT\deepcode-cli status --short
<LiMa repo test command discovered during Phase 0>
<LiMa focused test command if LiMa files are touched>
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT\deepcode-cli D:\GIT\docs\superpowers\plans\2026-05-23-lima-vibe-coding.md
```

Do not run unrestricted tests across `D:\GIT`; this workspace contains many unrelated local reference repositories.

---

## Success Criteria

The integration is successful when:

- LiMa can run locally from the user's fork.
- LiMa can call LiMa through an OpenAI-compatible profile.
- A toy coding task succeeds in a sandbox.
- LiMa's file/tool permissions are bounded.
- LiMa run results can be summarized back into LiMa memory/mastery.
- Real LiMa tasks are attempted only in isolated worktrees with explicit owner approval.

This gives LiMa a creative vibe coding surface while preserving LiMa's safety discipline.
