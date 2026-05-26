# LiMa Capability Hardening Scorecard

> Updated: 2026-05-26 (CAP-HARDEN-1 local closeout)
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
| Chat/IDE coding | 4 | Golden-path test `test_chat_ide_golden_path.py`; closeout writes `chat_ide` evidence; smoke `--golden-path-evidence` | VPS public golden-path smoke → score 5 |
| LiMa Code Worker | 3 | `/agent/tasks` result → `limacode_worker` evidence (existing) | Prompt contract + hooks + daily closeout |
| Device Gateway | 4 fake / 2 real | `/device/v1/tasks` → `device_gateway` evidence on queued/sent/failed | Real-device flash + motion smoke |
| Backend routing | 4 | `run_eval_full_and_report.py` → `backend_eval` evidence | Scheduled re-eval + admission report |
| Ops/learning | 4 | `ingest_task_outcome` → `ops_learning` evidence | Capability digest ranks next fixes |
| Code quality | 4 | 1891 tests, CI gates (pyright/deptry/ruff/pip-audit), module splits | Slice-level risk burn-down |
