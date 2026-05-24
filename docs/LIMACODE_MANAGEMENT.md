# LiMa Code Management

> Updated: 2026-05-24

## Purpose

LiMa Code is a first-class LiMa distribution and worker. The main LiMa
repository manages it through the `deepcode-cli` submodule, while LiMa Code
keeps its own source history in `https://github.com/zhuguang-ZFG/deepcode-cli`.

This keeps the boundary explicit:

- LiMa Server owns routing, memory, backend health, task contracts, VPS
  deployment, and safety gates.
- LiMa Code owns terminal coding workflow, local tool execution, MCP client
  behavior, worker loops, local audit files, and user-facing CLI behavior.
- The main repository owns the pinned LiMa Code revision, integration records,
  cross-repo contract tests, and release/deploy evidence.

## Repository Entry

| Path | Type | Remote | Branch |
|---|---|---|---|
| `deepcode-cli` | Git submodule | `https://github.com/zhuguang-ZFG/deepcode-cli.git` | `main` |

Current pinned revision:

```text
278a5f7 feat: add lima worker diagnostics
```

## Update Rules

1. Commit and push LiMa Code changes in `deepcode-cli` first.
2. Run the relevant LiMa Code checks in `deepcode-cli`.
3. Return to the main LiMa repository and stage only the updated submodule
   pointer plus related main-repo docs/tests.
4. If the Server/Worker task contract changes, update both repositories in
   the same closure and record the verification in `STATUS.md`,
   `docs/LIMA_MEMORY.md`, and `progress.md`.
5. Do not commit `.lima-code/` runtime state, local audit files, API keys,
   provider credentials, VPS secrets, or generated local task workspaces.

## Verification

Use these checks before advancing the submodule pointer:

```powershell
cd D:\GIT\deepcode-cli
npm.cmd test
npm.cmd run check
```

For Server/Worker integration changes, also verify from the main repo:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py tests\test_lima_code_dev_search_tools.py -q --ignore=active_model
```

For live-worker changes, run the documented smoke path in
`docs/LIMA_REAL_MACHINE_SMOKE.md` only after the local checks pass and the
target repository is allowlisted.

## Safety Boundary

LiMa Code may execute local commands only inside explicit allowlisted
repositories. The main LiMa repository remains the control plane for task
creation, audit expectations, model routing policy, and deployment records.

Always-on worker behavior remains gated by repo allowlist, worker budget, stop
marker, local audit, failure quarantine, and manual production approval.

## External Workflow References

These external projects are admitted as LiMa Code workflow references, not as
runtime dependencies:

- `can1357/oh-my-pi`: IDE-wired coding-agent UX, LSP/debug/tool harness, status
  panels, and local worker ergonomics.
- `openai/symphony`: isolated implementation runs, proof-of-work bundles, CI/PR
  evidence, and board-driven orchestration.
- `addyosmani/agent-skills`: engineering skill packaging, slash-command
  lifecycle, and explicit quality gates.
- `mattpocock/skills` and `walkinglabs/learn-harness-engineering`: small,
  composable, engineer-controlled skills and harness engineering practices.
- `warpdotdev/warp`: terminal command-block UX, agent panels, and recovery
  ergonomics; AGPL code remains concept-only unless separately reviewed.
- `nexu-io/open-design`: local-first design workbench and BYOK agent routing
  reference; external CLI discovery must stay allowlisted and opt-in.
- `pascalorg/editor`: 3D/canvas/editor interaction patterns for future
  visualization tools.
- `delibae/claude-prism`: offline-first scientific writing workspace and
  reproducible artifact posture.
- `wjn1996/HeavySkill`: opt-in heavy reasoning/evaluation pattern for hard
  planning or review tasks after license review.
- `Lum1104/Understand-Anything` and `zilliztech/claude-context`: semantic code
  search, graph context, and MCP packaging ideas for local coding sessions.
- `aattaran/deepclaude`: Anthropic-compatible backend-swap UX reference only.

Any adoption must preserve LiMa Server's backend admission, provider key
custody, repo allowlist, audit, review gates, and push/deploy approval rules.
