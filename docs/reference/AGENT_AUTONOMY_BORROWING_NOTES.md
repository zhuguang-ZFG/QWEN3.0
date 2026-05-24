# Agent Autonomy Borrowing Notes

## Borrowed Concepts

- OpenAI Agents-style guardrails, tracing, and explicit handoff boundaries.
- Google ADK-style separation between workflow/task state and production router hot path.
- GenericAgent-style layered memory and candidate skill extraction after verified task success.
- EvoMap-style gated promotion: candidates remain inactive until evaluation, manual approval, and evidence exist.
- Agency-agents-style role separation: planner, coder, reviewer, tester, and memory/evolution responsibilities stay distinct.
- Microsoft Agent Governance Toolkit-style governance metadata: risk class,
  allowed actions, policy trace, human approval requirement, and audit
  evidence.
- OpenAI Symphony-style isolated implementation runs and proof bundles, kept
  behind LiMa's existing Server/Worker approval gates.
- agent-skills and HeavySkill-style explicit workflow skills, quality gates,
  and opt-in deep reasoning for hard tasks.
- oh-my-pi-style local IDE/tool harness ergonomics for LiMa Code.
- deepclaude-style backend proxy ergonomics as a UX reference only, never as a
  bypass around LiMa provider admission or key custody.
- Sub-Agent versus Agent Team coordination boundary: default to isolated
  sub-agents for cleanly separable research, review, test, and verification
  work; upgrade to an Agent Team only when the task needs shared state, real-time
  communication, and long-lived coordination.

## Coordination Rule

- Start with one owner agent when tasks share deep context.
- Use sub-agents like isolated function calls: each receives a bounded context,
  independent tools, and returns a clean result to the owner.
- Do not split by generic roles such as planner, developer, and tester when the
  handoff would lose the intent, tradeoffs, or implementation context.
- Use Agent Teams only when agents must communicate during execution, react to
  each other's changes, or coordinate over a shared task/event layer.
- Before creating an Agent Team, require an explicit shared-state model,
  ownership map, audit trail, conflict policy, and stop/approval gate.

## Rejected Concepts

- Unbounded shell access.
- Fully autonomous production mutation.
- External worker pools.
- Dynamic package installation as a default behavior.
- Large persona-agent libraries before trace and approval gates are mature.
- Hidden autonomous model/provider swaps outside LiMa's routing registry.
- Skill packs that can change tool permissions, deployment behavior, or
  hardware access without explicit review.
- Multi-agent role sprawl where coordination overhead is larger than the task.
- Agent Teams without a shared task layer, event log, conflict policy, and
  explicit owner.

## LiMa Implementation

- Server task APIs and LiMa Code bounded worker loops provide the current agent workbench.
- Current default orchestration mode is owner-agent plus isolated sub-agents.
- Candidate skills are suggestion-only until manually promoted.
- Promotion now requires mastery evidence references in addition to evaluation and manual approval.
- Production deploys, VPS operations, GitHub pushes, credential changes, and destructive commands remain approval-gated.

## License Boundary

These references are used for architecture concepts only. Do not vendor or copy source code from reference projects unless a separate license review explicitly permits it.
