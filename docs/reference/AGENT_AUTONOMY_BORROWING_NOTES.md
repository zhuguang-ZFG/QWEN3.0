# Agent Autonomy Borrowing Notes

## Borrowed Concepts

- OpenAI Agents-style guardrails, tracing, and explicit handoff boundaries.
- Google ADK-style separation between workflow/task state and production router hot path.
- GenericAgent-style layered memory and candidate skill extraction after verified task success.
- EvoMap-style gated promotion: candidates remain inactive until evaluation, manual approval, and evidence exist.
- Agency-agents-style role separation: planner, coder, reviewer, tester, and memory/evolution responsibilities stay distinct.

## Rejected Concepts

- Unbounded shell access.
- Fully autonomous production mutation.
- External worker pools.
- Dynamic package installation as a default behavior.
- Large persona-agent libraries before trace and approval gates are mature.

## LiMa Implementation

- Server task APIs and LiMa Code bounded worker loops provide the current agent workbench.
- Candidate skills are suggestion-only until manually promoted.
- Promotion now requires mastery evidence references in addition to evaluation and manual approval.
- Production deploys, VPS operations, GitHub pushes, credential changes, and destructive commands remain approval-gated.

## License Boundary

These references are used for architecture concepts only. Do not vendor or copy source code from reference projects unless a separate license review explicitly permits it.
