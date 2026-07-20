# UI polish code review — 2026-07-20

> Scope: `07-20-ui-polish` (`chat-web/` + `esp32S_XYZ` manager-mobile).
> Full-project round1/round2 blockers are out of scope (already closed).

## Verdict

Implementation matches PRD Tier 0 + Tier 1 direction. Review found **3 Warnings** and **6 Suggestions**; all were fixed in the same session before commit.

## Findings (closed)

| ID | Severity | Issue | Fix |
|----|----------|--------|-----|
| W1 | Warning | Stream fail/abort left orphan AI bubble; retry stacked DOM | `removeUnfinalizedAiMessage` / `settleAbortedAiMessage` + `data-finalized` |
| W2 | Warning | Stop button showed spinner + stop-square | CSS: loading shows stop-square only |
| W3 | Warning | Device list refresh fail + cached rows double UI | Full-page error only when empty; banner when cache exists |
| S1 | Suggestion | task-status failed had no retry action | Emit `retry` → scroll to write-draw |
| S2 | Suggestion | `paramsSummary` double-called in template | `summaryByTaskId` computed |
| S3 | Suggestion | WiFi disabled reason always visible | Show after attempt / selected network |
| S4 | Suggestion | Pause confirm ambiguous vs ESTOP | i18n: soft pause, not emergency stop |
| S5 | Suggestion | `endCall` left `.error` on status | `classList.remove('error')` |
| S6 | Suggestion | Handwriting button spinner fragile | Page-local `.btn-spinner` |

## Gates

- `node --check` on all touched chat-web `.js`: pass
- `vue-tsc --noEmit` (manager-mobile): not re-run in this session — run before mobile release
- Backend / G-code: not touched — no `agent_gate`

## Residual (user / next)

- AC6 visual pass page-by-page (chat-web + 小程序)
- Tier 2 leftovers if any (voiceprint radius, privacy SectionCard, etc. per research inventory)
- Submodule branch at commit time: `fix/review-2026-07-20-h2-wdt-tasks` (mobile UI only in this change set)
