# LiMa Task Prompt Contract v0.1 (LC-W-1)

> **Status:** Active (next slice) | **Created:** 2026-05-26  
> **Parent:** [`docs/NEXT_MILESTONES.md`](../NEXT_MILESTONES.md) §2 LiMa Code Worker  
> **Depends on:** bounded `/lima task|next|work`, agent task store, summary constraints (existing)

---

## 1. Goal

Unify how LiMa **creates**, **stores**, and **renders** worker task prompts using a fixed KERNEL-style structure:

```text
Context / Task / Constraints / Verify / Output
```

So `/agent/tasks`, LiMa Code worker runs, role prompts, and skill activation all read the **same contract**, not ad-hoc `goal` + string list.

---

## 2. Non-goals (v0.1)

- Hooks + skill auto-activation (LC-W-2)
- Always-on daemon
- Policy guidelines engine (Parlant-style)
- Changing Telegram / GitHub notify paths

---

## 3. Current state (evidence)

| Layer | Today |
|-------|--------|
| Server | `TaskCreateBody`: `goal`, `constraints[]`, `test_commands[]`, `mode` — no structured sections |
| LiMa Code | `LiMaAgentTaskRequest.goal/constraints`; lifecycle hooks write markdown lists |
| Summary gate | `agent_runtime/summary_constraints.py` — required result fields |
| Artifacts | `deepcode-cli` `artifact-bundle.ts` — plan.md from goal/constraints |

---

## 4. Contract schema (v0.1)

Add optional field on task create/get (backward compatible):

```json
{
  "prompt_contract": {
    "context": "string, max 2000",
    "task": "string, max 1000",
    "constraints": ["string, max 500 each, max 20"],
    "verify": ["string, max 500 each, max 10"],
    "output": "string, max 1000"
  }
}
```

**Migration rule:** If `prompt_contract` absent, derive from legacy fields:

| Legacy | Maps to |
|--------|---------|
| `goal` | `task` |
| `constraints[]` | `constraints` |
| `test_commands[]` | `verify` |
| `mode` + summary rules | `output` template hint |

---

## 5. Render format (worker-facing)

Single markdown block injected before tools (LiMa Code + Server smoke tasks):

```markdown
## Context
{context or "(none)"}

## Task
{task}

## Constraints
- ...

## Verify
- ...

## Output
{output or default summary template}
```

Default **Output** when empty:

```text
Return needs_review with summary JSON: changed_files, tests_run, remaining_risks, review_status.
```

---

## 6. Implementation slices

| Step | ID | Files | Done when |
|------|-----|-------|-----------|
| 1 | LC-W-1a | `agent_runtime/prompt_contract.py` | parse, validate, legacy migrate, render |
| 2 | LC-W-1b | `routes/agent_tasks.py` schemas + create | API accepts `prompt_contract`; stores in task JSON |
| 3 | LC-W-1c | `deepcode-cli/src/lima/prompt-contract.ts` | mirror render; task-runner uses rendered block |
| 4 | LC-W-1d | `tests/test_prompt_contract*.py` + deepcode-cli unit | round-trip legacy + explicit contract |
| 5 | LC-W-1e | VPS smoke | one `/agent/tasks` create → `/lima next` → worker log shows 5 sections |

**Order:** 1 → 2 → tests → 3 → 5 (Server-first, then submodule).

**Progress 2026-05-26:** 1a–1d done locally; 1e VPS smoke pending.

---

## 7. Acceptance

- [x] POST `/agent/tasks` with only `goal` → stored task renders 5 sections
- [x] POST with full `prompt_contract` → worker prompt matches render golden
- [ ] Existing smokes (`worker/smoke-task`) unchanged behavior
- [ ] `progress.md` / `findings.md` closeout with test counts

---

## 8. Risks

- **Submodule drift:** deepcode-cli pin must bump after TS changes
- **Token budget:** cap section lengths (table above)
- **Do not** break `summary_constraints` gate — Output section must reference required summary fields

---

## 9. After v0.1

LC-W-2 Hooks + `.lima-code/dev/active/<task>/` per `task_plan.md` item 5.
