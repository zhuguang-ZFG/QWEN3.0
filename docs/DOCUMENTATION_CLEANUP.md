# Documentation Cleanup Queue

> Updated: 2026-05-27
> Scope: reduce doc noise without breaking current references.

## Current Inventory

- `docs/` contains about 175 markdown files.
- The active entrypoint is `docs/README.md`.
- `docs/DOCUMENTATION_STATUS.md` remains the compatibility map for older agents.
- The cleanup strategy is soft-archive first: mark and index before moving or
  deleting files.

## Keep Hot

These files should stay easy to find and should be updated when runtime facts
change:

| File | Reason |
|---|---|
| `../STATUS.md` | Short current operational snapshot. |
| `LIMA_MEMORY.md` | Durable memory and handoff facts. |
| `NEXT_MILESTONES.md` | Current priority order. |
| `REQUEST_PIPELINE_AUTHORITY.md` | Production chat pipeline authority. |
| `CAPABILITY_HARDENING_SCORECARD.md` | Capability score and next gates. |
| `FREE_MODEL_ROUTING_STATUS.md` | Backend routing evidence. |
| `LIMACODE_MANAGEMENT.md` | LiMa Code submodule governance. |
| `ESP32S_XYZ_MANAGEMENT.md` | Hardware/product submodule governance. |
| `ONLINE_DISTRIBUTIONS.md` | VPS and public endpoint ownership. |
| `DOCUMENTATION_STATUS.md` | Compatibility and drift rules. |

## Soft-Archived Categories

These should not drive new work unless a hot doc points to them:

| Pattern | Treatment |
|---|---|
| `docs/archive/code-quality/CQ014_*.md` | Historical refactor slice notes. |
| `docs/WECHAT_*.md` except `WECHAT_RETIRED.md` | Retired WeChat product notes. |
| `docs/superpowers/plans/2026-05-22-*.md` | Historical plans, mostly closed. |
| `docs/superpowers/plans/2026-05-23-*.md` | Historical reference and autonomy plans. |
| `docs/*_SMOKE.md` | Evidence records; keep, but do not treat as active plans. |
| `docs/*_INTEGRATION.md` | Runbooks; read only for that integration. |

## Next Physical Cleanup Batches

Do these only after a reference scan for each batch:

1. Move retired WeChat docs to `docs/archive/wechat-retired/`.
2. Move closed 2026-05-22 and 2026-05-23 plans to
   `docs/archive/superpowers-plans/`.
3. Add redirect stubs only for files still referenced by scripts or active docs.
4. Update `DOCUMENTATION_STATUS.md` after each batch.

## Completed Cleanup Batches

| Date | Batch | Evidence |
|---|---|---|
| 2026-05-27 | Moved `docs/CQ014_*.md` to `docs/archive/code-quality/` | Reference scan found only historical `progress.md` mentions plus cleanup docs. |

## Safety Rules

- Do not delete docs in the first cleanup pass.
- Do not move files with uncommitted edits.
- Do not move a doc referenced by code, scripts, or active docs without either
  updating the reference or leaving a redirect stub.
- Do not treat unchecked boxes in old plans as open work. Use
  `NEXT_MILESTONES.md`, `progress.md`, and `findings.md`.
