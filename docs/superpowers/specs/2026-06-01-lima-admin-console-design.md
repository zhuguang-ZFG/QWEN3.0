# LiMa Admin Console Design

## Goal

Build a practical production admin console for LiMa Router that is useful during daily operations, not only a demo page. The console must expose the current backend health, request traffic, model fallback signals, retrieval traces, agent task audit, and safe operator actions from the existing `/admin/api/*` surface.

## Design System

Using the `ui-ux-pro-max` guidance, the console uses an AI-native dark dashboard style with bento cards, high-contrast status colors, compact data tables, and clear operator hierarchy:

- **AI-Native UI + Bento Dashboard**: quick status cards first, details in panels.
- **Dark Mode OLED**: low eye strain for long monitoring sessions.
- **Accessible status color**: green/amber/red badges with text labels, not color-only status.
- **Operator-first density**: tables are compact but searchable and scannable.
- **No destructive surprise**: mutating operations require explicit button actions and use existing CSRF/admin guards.

## Functional Scope

The first production version is a single static HTML page rendered from `routes/admin_ui.py` and backed by existing endpoints:

- `/admin/api/stats`: traffic, uptime, latency, backend call totals, intent and IDE distribution.
- `/admin/api/logs`: recent request log table.
- `/admin/api/backends`: backend inventory, enable/disable, test, add, delete.
- `/admin/api/model-status`: fallback count and retraining metadata.
- `/admin/api/retrieval-traces`: recent retrieval pipeline traces.
- `/admin/api/agent-audit`: recent LiMa Code/agent task audit.
- `/admin/api/retrain`: guarded retrain trigger.

## Constraints

- No frontend build step; the panel must remain deployable as Python-rendered HTML.
- No new external JS/CSS dependencies; this avoids CDN and supply-chain risk on admin pages.
- Preserve existing admin authentication and CSRF behavior.
- Keep secrets out of the UI; backend keys must never be rendered.
