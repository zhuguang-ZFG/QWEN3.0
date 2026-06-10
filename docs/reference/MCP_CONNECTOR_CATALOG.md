# MCP Connector Catalog

> Updated: 2026-05-26
> Scope: candidate MCP connectors for LiMa Server and Agent Worker.

## Purpose

Skills and MCP have different jobs:

- Skills teach LiMa how to think, review, test, and package work.
- MCP connectors give LiMa permissioned places to act.

This catalog is not an install list. A connector becomes usable only after it
has a task need, owner, allowlist, credential boundary, audit event, timeout,
and failure mode. Default Agent Worker sessions should receive only the smallest
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
| LiMa dev-search MCP tools | active | On only for Agent Worker tasks that request docs/error/source lookup | Existing tools: `dev_search_docs`, `dev_search_error`, `dev_read_url`, `dev_fetch_github_file`, `dev_summarize_sources`; read-only, SSRF-guarded, redacted. |
| Filesystem MCP | candidate | Off | Allowlisted repositories only; read-only by default; write requires task-scoped approval. |
| Git MCP | candidate | Off | Read/search/status first; branch, commit, and push actions require explicit approval gates. |
| Memory MCP | concept | Off | Borrow knowledge-graph memory shape; LiMa keeps typed memory, promotion evidence, and secret redaction as the active store. |
| Sequential Thinking MCP | concept | Off | Use only as an explicit, auditable hard-task workflow; never hidden default reasoning. |
| Time MCP | candidate | Off | Low-risk utility after logging and timezone behavior are stable. |
| Context7-style docs lookup | candidate | Off | Preferred for versioned library docs; no secrets or private source sent in queries. |
| Google Developer Knowledge MCP | candidate | Off | Useful for Google developer docs lookup; no private code, credentials, or cloud-resource mutations in queries. |

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
| Google MCP managed remote servers | candidate | Off | BigQuery, Cloud SQL, AlloyDB, Spanner, Firestore, GCE, GKE, Cloud Run, Storage, Maps, Chronicle, and related Google services require IAM scope, billing/cost caps, data-residency review, audit, timeout, and rollback owner. |
| Google open-source MCP servers | candidate | Off | Workspace, Firebase, Cloud Run, Analytics, gcloud, GCS, GKE, Security, Chrome DevTools, and genmedia connectors require per-server license/security review and least-privilege credentials. |
| RuVector MCP | concept | Off | Adaptive vector/graph memory reference only until LiMa benchmarks quality, latency, data migration, retention, and drift behavior. |

## Productivity, Business, Data, And Media

| Connector | Status | Default | LiMa boundary |
|---|---|---|---|
| Notion, Slack, Gmail, Jira, Asana MCP | candidate | Off | Account connectors require consent, workspace scope, outbound-message approval, and audit. |
| Stripe, HubSpot MCP | blocked | Off | Payment/CRM actions are out of current private coding-assistant scope. |
| Firecrawl MCP | candidate | Off | Useful for web extraction; license signals across Firecrawl packages must be reviewed per package before use. |
| Hyperbrowser-style browser automation | concept | Off | Browser app/extraction reference only. Any adapter requires API-key custody, target-site terms, privacy review, rate limits, and anti-abuse policy. |
| Agent-Reach connectors | concept | Off | Internet-reach scaffold for web, video, RSS, GitHub, and social sources. Cookie/social/proxy/shell-installed tools and posting actions require consent, account isolation, platform-term review, and redacted credential storage. |
| cc-connect messaging bridge | concept | Off | Messaging bridge reference for Feishu/Lark, WeChat, Telegram, Slack, Discord, Weibo, voice/images, cron, hooks, and mobile chat UX. Outbound messaging and shell/admin commands require explicit approval and audit. |
| bluebox web-routine extraction | concept | Off | Routine discovery and closed-API extraction reference; requires target-site policy, anti-abuse review, API-key custody, and evidence logs before evaluation. |
| VidBee-style media ingestion | concept | Off | Video/audio/RSS downloader and progress-event reference only; copyright, target terms, storage, and consent gates are mandatory. |
| Browserbase, Bright Data, Apify MCP | concept | Off | Scraping/browser-scale tools require target-site policy, rate-limit, privacy, and anti-abuse review. |
| Figma MCP | concept | Off | Design read/import only until a UI workflow exists; no automatic code landing. |
| ElevenLabs MCP | concept | Off | Voice generation requires consent, voice license, storage, and cost controls. |
| Tavily MCP | candidate | Off | Search/extract/map/crawl candidate behind privacy, quota, cache, and citation policy. |
| searchcode MCP | candidate | Off | Public GitHub/open-source code intelligence (beta). **Public repos only**; never send LiMa private code. |
| codesearch MCP | candidate | Off | Local offline multi-repo semantic search (Rust, BM25 + vector + tree-sitter). Path allowlist required; enhances Agent Worker over raw `rg`. |
| Netdata MCP | candidate | Off | VPS/host diagnostics: CPU, memory, disk, processes, network, alerts via Netdata Agent MCP. Read-only first; see `docs/superpowers/plans/2026-05-26-lima-productivity-enhancement.md` PE-C-1. |
| Magic MCP | concept | Off | UI-generation workflow reference; generated code must go through Agent Worker review and tests. |
| last30days-style skill connectors | concept | Off | Time-bounded social/source search can inform research tasks only with BYO-key consent, platform-term review, attribution, and privacy boundaries. |
| Sirchmunk-style raw-file search MCP | concept | Off | Useful for local/remote raw-data search and streaming evidence logs; requires path allowlists, secret redaction, cache retention, and audit before use. |
| Nunchi agent-cli MCP | blocked | Off | Trading/finance tooling is not part of LiMa's coding/hardware scope. Borrow MCP-surface shape only; do not enable financial actions. |

## Discovery Sources

- Official MCP Registry: `https://registry.modelcontextprotocol.io/`
- Glama MCP Registry: `https://glama.ai/mcp/servers`
- SafeMCP (categorized list): `https://safemcp.com/`
- Official reference servers: `https://github.com/modelcontextprotocol/servers`
- Google MCP catalog: `https://github.com/google/mcp`
- Community list: `https://github.com/wong2/awesome-mcp-servers`
- Online runtime reference: `https://turbomcp.ai/`

**LiMa MCP radar (PE-A-1):** read-only inventory from Glama + Official Registry + SafeMCP →
`data/mcp_registry_snapshot.json` → candidate rows in this catalog.
Script: `scripts/inventory_mcp_registries.py` (run 2026-05-26).

The official reference server repository says its servers demonstrate MCP
features and SDK usage and are educational examples, not production-ready
solutions. LiMa must review and wrap every connector before production use.
