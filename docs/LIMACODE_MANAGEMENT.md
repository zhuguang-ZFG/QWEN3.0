# LiMa Code Management

> Updated: 2026-05-24

## Purpose

LiMa Code is a first-class LiMa distribution and worker. The main LiMa
repository manages it through the `deepcode-cli` submodule, while LiMa Code
keeps its own source history in `https://github.com/zhuguang-ZFG/deepcode-cli`.

This keeps the boundary explicit:

- LiMa Server owns routing, memory, backend health, task contracts, VPS
  deployment, and safety gates.
- LiMa Code owns terminal coding workflow, local tool execution, MCP client
  behavior, worker loops, local audit files, and user-facing CLI behavior.
- The main repository owns the pinned LiMa Code revision, integration records,
  cross-repo contract tests, and release/deploy evidence.

## Repository Entry

| Path | Type | Remote | Branch |
|---|---|---|---|
| `deepcode-cli` | Git submodule | `https://github.com/zhuguang-ZFG/deepcode-cli.git` | `main` |

Current pinned revision:

```text
278a5f7 feat: add lima worker diagnostics
```

## Update Rules

1. Commit and push LiMa Code changes in `deepcode-cli` first.
2. Run the relevant LiMa Code checks in `deepcode-cli`.
3. Return to the main LiMa repository and stage only the updated submodule
   pointer plus related main-repo docs/tests.
4. If the Server/Worker task contract changes, update both repositories in
   the same closure and record the verification in `STATUS.md`,
   `docs/LIMA_MEMORY.md`, and `progress.md`.
5. Do not commit `.lima-code/` runtime state, local audit files, API keys,
   provider credentials, VPS secrets, or generated local task workspaces.

## Verification

Use these checks before advancing the submodule pointer:

```powershell
cd D:\GIT\deepcode-cli
npm.cmd test
npm.cmd run check
```

For Server/Worker integration changes, also verify from the main repo:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_agent_task_routes.py tests\test_lima_code_dev_search_tools.py -q --ignore=active_model
```

For live-worker changes, run the documented smoke path in
`docs/LIMA_REAL_MACHINE_SMOKE.md` only after the local checks pass and the
target repository is allowlisted.

## Safety Boundary

LiMa Code may execute local commands only inside explicit allowlisted
repositories. The main LiMa repository remains the control plane for task
creation, audit expectations, model routing policy, and deployment records.

Always-on worker behavior remains gated by repo allowlist, worker budget, stop
marker, local audit, failure quarantine, and manual production approval.

MCP connector use follows `docs/reference/MCP_CONNECTOR_CATALOG.md`:

- Default to read-only tools and task-scoped enablement.
- Do not keep broad MCP schemas resident in every coding session.
- Keep API keys, cookies, database credentials, cloud tokens, and browser
  session secrets out of model-visible context.
- Require approval before any MCP tool can write GitHub state, mutate files,
  run shell commands, change databases, deploy services, send messages, spend
  money, or touch hardware.
- Prefer LiMa-owned dev-search tools for docs/error/source lookup before adding
  external search or extraction connectors.

## External Workflow References

These external projects are admitted as LiMa Code workflow references, not as
runtime dependencies:

- `can1357/oh-my-pi`: IDE-wired coding-agent UX, LSP/debug/tool harness, status
  panels, and local worker ergonomics.
- `openai/symphony`: isolated implementation runs, proof-of-work bundles, CI/PR
  evidence, and board-driven orchestration.
- `addyosmani/agent-skills`: engineering skill packaging, slash-command
  lifecycle, and explicit quality gates.
- `mattpocock/skills` and `walkinglabs/learn-harness-engineering`: small,
  composable, engineer-controlled skills and harness engineering practices.
- `warpdotdev/warp`: terminal command-block UX, agent panels, and recovery
  ergonomics; AGPL code remains concept-only unless separately reviewed.
- `nexu-io/open-design`: local-first design workbench and BYOK agent routing
  reference; external CLI discovery must stay allowlisted and opt-in.
- `pascalorg/editor`: 3D/canvas/editor interaction patterns for future
  visualization tools.
- `delibae/claude-prism`: offline-first scientific writing workspace and
  reproducible artifact posture.
- `wjn1996/HeavySkill`: opt-in heavy reasoning/evaluation pattern for hard
  planning or review tasks after license review.
- `Lum1104/Understand-Anything` and `zilliztech/claude-context`: semantic code
  search, graph context, and MCP packaging ideas for local coding sessions.
- `aattaran/deepclaude`: Anthropic-compatible backend-swap UX reference only.
- Official MCP Registry, `modelcontextprotocol/servers`, and
  `wong2/awesome-mcp-servers`: discovery inputs for a reviewed MCP connector
  catalog; not a default install bundle.
- Context7, Tavily, Firecrawl, GitHub MCP, Playwright MCP, Filesystem, Git,
  Memory, Sequential Thinking, Postgres, and Magic MCP remain candidate
  connectors behind the catalog. Each needs a per-task allowlist, credential
  boundary, and audit path before LiMa Code can use it.
- `calesthio/OpenMontage`: AGPL concept-only reference for agentic media
  pipeline staging, artifact quality gates, provider boundaries, and
  skill/tool catalog structure.
- `firecrawl/open-lovable`: MIT reference for website-to-React reconstruction
  and sandboxed app generation. Scraping, external API keys, sandbox providers,
  and generated code must stay opt-in and review/test gated.
- `repowise-dev/claude-code-prompts`: MIT reference for prompt-contract
  structure, tool-specific instructions, verification prompts, memory prompts,
  and coordinator/delegation boundaries.
- `VoltAgent/awesome-codex-subagents`: MIT reference for Codex-native subagent
  metadata, category naming, sandbox defaults, and explicit delegation. Do not
  install broad subagent libraries by default.
- `anomalyco/opencode`: MIT reference for coding-agent terminal UI, packaging,
  installer channels, desktop app posture, localization, and workflow
  ergonomics.
- `2025Emma/vibe-coding-cn`: MIT Chinese Vibe Coding guide reference for
  planning-first onboarding, prompt/skill catalog organization, and
  AI-pair-programming education.
- `mvanhorn/last30days-skill`: MIT reference for time-bounded research skills
  and social-source scoring; BYO keys/browser sessions, platform terms,
  attribution, and privacy boundaries are mandatory before use.
- `alchaincyf/hermes-agent-orange-book`: non-commercial guide reference for
  Hermes-style learning loops, memory layering, skill creation, and tool
  orchestration vocabulary; do not copy content into runtime prompts.
- `claude.com/resources/use-cases`: official product use-case taxonomy
  reference for workflow examples and onboarding categories; do not scrape or
  copy page content into LiMa without review.
- TUNA mirror service: operational reference for China-network dependency
  bootstrap and fallback mirror documentation, not a code dependency.
- `modelscope/sirchmunk`: Apache-2.0 reference for raw-file/indexless search,
  evidence sampling, streaming search logs, self-evolving knowledge clusters,
  and local/remote path allowlists. Use as a search architecture input, not as
  a replacement for LiMa memory or graph APIs.
- `hyperbrowserai/hyperbrowser-app-examples`: browser automation and data
  extraction app reference. Keep API keys, scraping targets, privacy, target
  terms, and anti-abuse policy behind explicit review.
- `garrytan/gstack`: MIT reference for stage-gated LiMa Code workflows:
  office-hours/planning, review, browser QA, security audit, release, safety
  guard commands, cross-model second opinion, and memory sync. Do not install
  the full skill stack by default or introduce broad role sprawl.
- `Nunchi-trade/agent-cli`: MIT reference for agent skills, MCP surfaces,
  deterministic orchestrators, risk states, reconciliation, HTTP/SSE
  observability, and REFLECT-style scheduled review. Trading and financial
  automation remain out of scope and blocked.
- `Gen-Verse/OpenClaw-RL`: Apache-2.0 research reference for feedback-to-eval/
  training loops. Live self-training from private LiMa sessions is blocked
  until consent, privacy, eval, rollback, model-storage, and cost gates exist.
- `666ghj/MiroFish`: AGPL concept-only reference for swarm simulation and
  scenario/prediction UX; no code copy and no prediction-driven actions.
- `https://hermes-agent.nousresearch.com/`: official Hermes Agent site used as
  a capability benchmark for server-resident agents, scheduled automations,
  persistent memory, generated skills, isolated subagents, sandboxing, browser
  control, and messaging surfaces. Site license claims require source-level
  verification before code reliance.
- Feishu `2026 企业级AI编程实践手册`: methodology background for context
  engineering, specs, rules, skills, MCP, and enterprise AI coding process.
  No text or document structure should be reused without license/permission
  review.
- `langflow-ai/openrag`: Apache-2.0 reference for document ingestion,
  Docling-style parsing, retrieval observability, reranking, chat UI, and
  Langflow/OpenSearch workflow shape. Do not adopt the full platform as a
  LiMa Code dependency.
- `GoogleCloudPlatform/generative-ai`: Apache-2.0 reference for Gemini,
  Agent Platform, Agent Search, RAG/grounding, vision, audio, and setup
  samples. Google Cloud usage remains optional and provider-gated.
- `ruvnet/RuVector`: MIT reference for adaptive vector/graph memory,
  PostgreSQL integration, local/WASM retrieval, MCP, branchable data, and audit
  chains. Claims must be benchmarked before any LiMa storage change.
- `Panniantong/Agent-Reach`: MIT reference for internet-reach scaffolding,
  channel health checks, and practical web/video/RSS/social/GitHub connectors.
  Cookie/social/proxy/shell setup remains explicit opt-in.
- `chenhg5/cc-connect`: README badge says MIT, but raw license fetch failed in
  this review. Use as a messaging/admin bridge UX reference only; messaging
  actions require allowlists, credential custody, approval, and audit.
- `VectorlyApp/bluebox`: Apache-2.0 reference for web-routine discovery,
  parallel extraction, browser fallback, and context replay. Closed-API or
  reverse-engineering behavior is default-off behind target policy.
- `nexmoe/VidBee`: MIT reference for media-ingestion UX, yt-dlp/ffmpeg task
  queues, RSS auto-download, API/SSE events, and Docker/web packaging. Respect
  copyright, target-site terms, storage, and consent gates.
- `google/mcp`: Apache-2.0 reference for Google MCP catalog and Cloud Run
  hosting patterns. Cloud, Workspace, database, Maps, DevTools, security, and
  storage connectors remain default-off behind IAM, billing, data, and audit
  gates.
- `ruvnet/RuView`: MIT reference for ESP32/WiFi CSI sensing workflows,
  hardware witness logs, Home Assistant/Matter bridge ideas, and Codex/Claude
  hardware workflow plugin shape. Do not install the plugin or enable people,
  vital-sign, fall, through-wall, security, or medical sensing without explicit
  consent, privacy/legal review, calibrated hardware evidence, retention rules,
  and approval gates.

Any adoption must preserve LiMa Server's backend admission, provider key
custody, repo allowlist, audit, review gates, and push/deploy approval rules.
