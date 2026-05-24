# MCP Connector Catalog

> Updated: 2026-05-24
> Scope: candidate MCP connectors for LiMa Server and LiMa Code.

## Purpose

Skills and MCP have different jobs:

- Skills teach LiMa how to think, review, test, and package work.
- MCP connectors give LiMa permissioned places to act.

This catalog is not an install list. A connector becomes usable only after it
has a task need, owner, allowlist, credential boundary, audit event, timeout,
and failure mode. Default LiMa Code sessions should receive only the smallest
tool set needed for the current task.

## Status Legend

| Status | Meaning |
|---|---|
| `active` | Already implemented inside LiMa-owned code. |
| `candidate` | Safe to evaluate behind review gates. |
| `concept` | Useful as a design reference, not ready to install. |
| `blocked` | Do not enable until legal/security/privacy review changes. |

## Foundation Connectors

| Connector | Status | Default | LiMa boundary |
|---|---|---|---|
| LiMa dev-search MCP tools | active | On only for LiMa Code tasks that request docs/error/source lookup | Existing tools: `dev_search_docs`, `dev_search_error`, `dev_read_url`, `dev_fetch_github_file`, `dev_summarize_sources`; read-only, SSRF-guarded, redacted. |
| Filesystem MCP | candidate | Off | Allowlisted repositories only; read-only by default; write requires task-scoped approval. |
| Git MCP | candidate | Off | Read/search/status first; branch, commit, and push actions require explicit approval gates. |
| Memory MCP | concept | Off | Borrow knowledge-graph memory shape; LiMa keeps typed memory, promotion evidence, and secret redaction as the active store. |
| Sequential Thinking MCP | concept | Off | Use only as an explicit, auditable hard-task workflow; never hidden default reasoning. |
| Time MCP | candidate | Off | Low-risk utility after logging and timezone behavior are stable. |
| Context7-style docs lookup | candidate | Off | Preferred for versioned library docs; no secrets or private source sent in queries. |

## Coding And Stack Connectors

| Connector | Status | Default | LiMa boundary |
|---|---|---|---|
| GitHub MCP | candidate | Off | Repo/issue/PR/Actions reads first; write, merge, release, or secret operations require approval and audit. |
| Playwright MCP | candidate | Off | Use for long-state browser verification and screenshots; prefer CLI/skill flows for simple checks to control token use. |
| Sentry MCP | candidate | Off | Read-only issue/stack access; production data must be redacted before model context. |
| Semgrep MCP | candidate | Off | Security scan input only; findings require human review before code changes. |
| CircleCI or CI MCP | candidate | Off | Read logs and rerun approved jobs only; do not mutate pipeline settings by default. |
| Postgres or Neon MCP | candidate | Off | Schema/read-only queries first; migrations require database migration plan and backup evidence. |
| Supabase MCP | candidate | Off | Auth/storage/functions operations require separate service-owner review. |
| Neo4j MCP | concept | Off | Useful for graph diagnostics only after LiMa graph index exists. |
| Qdrant MCP | concept | Off | Candidate for vector memory only after retention, privacy, and rebuild policy are defined. |
| Tinybird MCP | concept | Off | Analytics reference only; no business data connector without privacy review. |
| AWS, Cloudflare, Grafana, Railway, Render MCP | candidate | Off | Cloud/deploy/observability tools require environment allowlist, approval, and rollback owner. |

## Productivity, Business, Data, And Media

| Connector | Status | Default | LiMa boundary |
|---|---|---|---|
| Notion, Slack, Gmail, Jira, Asana MCP | candidate | Off | Account connectors require consent, workspace scope, outbound-message approval, and audit. |
| Stripe, HubSpot MCP | blocked | Off | Payment/CRM actions are out of current private coding-assistant scope. |
| Firecrawl MCP | candidate | Off | Useful for web extraction; license signals across Firecrawl packages must be reviewed per package before use. |
| Browserbase, Bright Data, Apify MCP | concept | Off | Scraping/browser-scale tools require target-site policy, rate-limit, privacy, and anti-abuse review. |
| Figma MCP | concept | Off | Design read/import only until a UI workflow exists; no automatic code landing. |
| ElevenLabs MCP | concept | Off | Voice generation requires consent, voice license, storage, and cost controls. |
| Tavily MCP | candidate | Off | Search/extract/map/crawl candidate behind privacy, quota, cache, and citation policy. |
| Magic MCP | concept | Off | UI-generation workflow reference; generated code must go through LiMa Code review and tests. |

## Discovery Sources

- Official MCP Registry: `https://registry.modelcontextprotocol.io/`
- Official reference servers: `https://github.com/modelcontextprotocol/servers`
- Community list: `https://github.com/wong2/awesome-mcp-servers`
- Online runtime reference: `https://turbomcp.ai/`

The official reference server repository says its servers demonstrate MCP
features and SDK usage and are educational examples, not production-ready
solutions. LiMa must review and wrap every connector before production use.
