# Free Web AI Admission

> Updated: 2026-05-22
> Private code remains disabled for no-login web candidates unless a candidate is explicitly admitted and trusted.

| ID | Probe | Reverse Status | Admission | Route | Private Code | Reason |
|---|---|---|---|---|---|---|
| duck_ai | ok | already_reversed_local | admitted_late_fallback | True | False | local adapter and route admission evidence exist |
| heck_ai | ok | adapter_draft_exists | adapter_draft_pending | False | False | adapter draft exists but model smoke is not admitted |
| hix_chat | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| gpt_chat | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| deep_seek_mirror | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| plai_chat | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| deep_seek_ai | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| glm_ai_chat | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| instantseek | unknown_error | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |
| chat_gpt_org | ok | not_reversed_page_only | sandbox_only | False | False | reachable page-only candidate; no hot-path adapter |

## Decision

Only already-reversed, measured adapters may enter LiMa routing, and only as late fallback unless coding admission promotes them. Page-only candidates stay sandboxed.
