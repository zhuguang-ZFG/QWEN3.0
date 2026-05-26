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
| LiMa Code Worker | 3 | `/agent/tasks`, public task smoke, artifact bundles, learning loop | Prompt contract + hooks + daily closeout |
| Device Gateway | 4 fake / 2 real | Redis HA, fake-U8 public WSS smoke, path pipeline | Real-device flash + motion smoke |
| Backend routing | 4 | SCNet/Kimi/Cloudflare eval docs and JSON | Scheduled re-eval + admission report |
| Ops/learning | 4 | Outcome Ledger, shadow_mode, /digest, /dashboard, /inbox | Capability digest ranks next fixes |
| Code quality | 4 | 1891 tests, CI gates (pyright/deptry/ruff/pip-audit), module splits | Slice-level risk burn-down |
