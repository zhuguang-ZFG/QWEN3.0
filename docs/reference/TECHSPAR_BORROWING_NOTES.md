# TechSpar Borrowing Notes

## Borrowed Concepts

- Shared long-term mastery profile across coding, review, tests, deploys, and agent work.
- Weak-point extraction from failed tests, review findings, routing failures, deploy incidents, and blocked tool calls.
- Mastery updates that preserve history instead of erasing old failures after a fix.
- SM-2-inspired review scheduling for modules and weak points.
- Dynamic next-round focus: recommend tests and reviews based on evidence, not static checklists alone.

## Rejected Concepts

- Interview product UI.
- Voice stack.
- Resume and JD business workflows.
- User-facing React shell.
- Any direct runtime dependency on TechSpar.

## License Boundary

TechSpar is treated as a concept reference only. Do not copy code, assets, prompts, schemas, or UI from TechSpar into LiMa without a separate license review.

## LiMa Implementation

- `mastery_loop/` owns typed records, SQLite-backed storage, event adapters, scoring, weak-point extraction, review scheduling, recommendations, and recommendation traces.
- `agent_evolution.promote_candidate()` now requires mastery evidence references before a candidate can activate.
- The mastery loop is local and evidence-only in this pass; it does not automatically deploy, mutate production, or change hot-path routing.
