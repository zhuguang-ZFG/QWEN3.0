# External Capability Radar

> Date: 2026-05-24
> Scope: evaluate user-provided external references as capability inputs for
> LiMa Server, LiMa Code, and `esp32S_XYZ`.

## Rules

- Treat this as a capability map, not a code import list.
- Do not copy code from repositories with missing, GPL, or AGPL license signals.
- Before adopting any dependency, perform a per-repo license, security, secret,
  dependency, and maintenance review.
- Prefer local adapters, small tests, and reversible integration slices over
  large framework rewrites.

## Capability Groups

| Group | References | LiMa target |
|---|---|---|
| Static analysis, RAG, and code intelligence | Pyrefly, LightRAG, Sirchmunk, GitNexus, code-review-graph, graphify, gitreverse, Understand-Anything, claude-context | Main repo quality gates, LiMa Code context, graph/vector/indexless retrieval, review and repository understanding |
| Memory and agent knowledge | stash, hindsight, gbrain, rowboat | Durable memory, episode/fact separation, learning loops, agent state |
| Agent orchestration, skills, and workflow | OpenAI Agents SDK, Google ADK, GenericAgent, Evolver, Hermes Agent, Hermes Agent Orange Book, AutoResearchClaw, OpenClaw-RL, gstack, agent-cli, awesome-codex-subagents, open-agents, Symphony, PraisonAI, agency-agents, goclaw, oh-my-codex, oh-my-pi, clawsweeper, agent-skills, last30days skill, mattpocock skills, HeavySkill, learn-harness-engineering, claude-code-prompts, vibe-vibe, vibe-coding-cn | Controlled multi-agent work, hooks, review queues, issue/PR triage, skill packaging, harness engineering, work-run isolation, feedback/eval loops |
| MCP access plane and tool connectors | Official MCP Registry, modelcontextprotocol reference servers, awesome-mcp-servers, TurboMCP, GitHub/Playwright/Sentry/Semgrep/CircleCI/Postgres/Supabase/Neo4j/Qdrant/Tinybird/AWS/Cloudflare/Grafana/Railway/Render/Notion/Slack/Gmail/Jira/Asana/Stripe/HubSpot/Firecrawl/Browserbase/Bright Data/Apify/Memory/Sequential Thinking/Context7/Figma/ElevenLabs MCP references | Permissioned tool access, connector catalog, deployment gates, audit, and least-privilege MCP enablement |
| Governance, secure execution, and browser work | Microsoft Agent Governance Toolkit, CubeSandbox, browser-harness, CloakBrowser, Hyperbrowser examples, gstack browser/QA patterns | Safer worker execution, browser task verification, VPS/local isolation, governance policy, browser task artifacts |
| IDE, terminal, design, and workspace UX | Warp, Pascal Editor, ClaudePrism, Open Design, OpenCode, open-lovable, vibe-coding-cn | LiMa Code terminal UX, local design workspace, website-to-app workflows, scientific writing workspace, 3D/design editor patterns |
| Search, research, trends, and knowledge products | AnySearch Skill, last30days skill, Claude use cases, ml-intern, AutoResearchClaw, Sirchmunk, OmniScientist, Feynman, TrendRadar, HF Viewer, Youdao Baoku, Feishu 2026 enterprise AI programming handbook, Flipbook, OpenMontage, Algebrica, GLM-OCR | Research agents, trend monitors, product use-case taxonomy, model inspection, search extraction, document-to-brief/PPT/mind-map/video, OCR, visual browsing, enterprise AI coding methodology |
| Infrastructure mirrors and dependency resilience | Tsinghua Open Source Mirror (TUNA) | VPS and China-network dependency install acceleration, fallback mirrors, reproducible bootstrap documentation |
| Persona, style, and companion behavior | awesome-persona-distill-skills, WeClone, Feynman, ElatoAI, PersonaPlex, pocket-tts, VoxCPM | User style modeling, companion UX, voice/display persona boundaries |
| Hardware, robotics, and world models | ElatoAI, PersonaPlex, oh-my-pi, GR00T-WholeBodyControl, OpenClaw-RL, MiroFish, pocket-tts, VoxCPM, nano-world-model, ESP32 display references already tracked separately | Device Gateway voice/display/companion expansion after writing-machine gates, simulation/evaluation before real hardware |

## Source Evaluation

| Source | Observed capability | License signal | Borrow for LiMa | Target repo |
|---|---|---|---|---|
| `facebook/pyrefly` | Fast Python type checker and language server with gradual adoption tools. | MIT | Add optional focused type-check lane for stable Python modules before expanding to the whole repo. | Main, LiMa Code |
| `HKUDS/LightRAG` | Simple and fast retrieval-augmented generation with graph/RAG storage, multimodal parsing, chunking strategies, and role-specific LLM configuration. | MIT | Strengthen LiMa's graph/vector retrieval roadmap, retrieval trace discipline, multimodal ingestion boundary, and role-specific extraction/query/VLM separation. | Main, LiMa Code |
| `modelscope/sirchmunk` | Agentic search over raw data with indexless retrieval, knowledge clustering, Monte Carlo evidence sampling, self-evolving knowledge clusters, real-time chat, API/SSE, DuckDB persistence, and MCP support. | Apache-2.0 | Reference for raw-file search, evidence sampling, live knowledge evolution, local/remote path allowlists, streaming search logs, and low-infrastructure retrieval. Do not replace LiMa memory/RAG until interfaces and privacy gates exist. | Main, LiMa Code |
| `huggingface/ml-intern` | ML engineering agent that researches papers/docs/datasets and ships ML code. | Apache-2.0 | Borrow research-to-implementation loop for model evaluation, benchmark, and ML adapter tasks. | Main |
| `abhigyanpatwari/GitNexus` | Browser-side code knowledge graph and Graph RAG exploration. | No standard license in API metadata | Concept-only reference for local repository graph browsing and zero-server code exploration. | Main, LiMa Code |
| `alash3al/stash` | Persistent agent memory with episodes, facts, working context, Postgres, and MCP. | Apache-2.0 | Borrow memory taxonomy and MCP memory interface ideas for LiMa memory storage. | Main, LiMa Code |
| `openclaw/clawsweeper` | Scheduled issue/PR close recommendations. | MIT | Add future GitHub hygiene job for stale plans, issues, PRs, and close candidates. | Main |
| `mattpocock/skills` | Small, composable engineering skills for AI coding agents. | MIT | Strong reference for LiMa Code skill shape: small, adaptable, explicit, and engineer-controlled rather than monolithic process ownership. | LiMa Code, Main |
| `hfviewer.com` | Web product for inspecting and understanding Hugging Face models. | Website, no repo/license reviewed | Product reference for model-card/model-architecture inspection UX; no scraping or data dependency without review. | Main |
| `warpdotdev/warp` | Agentic development environment and terminal. | AGPL-3.0 | Concept-only for terminal/workspace UX, command blocks, agent panels, and local developer flow; no code copy. | LiMa Code |
| `pascalorg/editor` | React Three Fiber/WebGPU 3D building editor. | MIT | Reference for future design/canvas/3D workspace patterns; useful for visualization tooling, not current Device Gateway runtime. | Main, LiMa Code |
| `delibae/claude-prism` | Offline-first scientific writing workspace with LaTeX, Python, and scientific skills. | MIT | Reference for local-first research/writing workspaces, skill packs, and reproducible scientific artifacts. | Main, LiMa Code |
| `nexu-io/open-design` | Local-first open-source Claude Design alternative with many coding-agent CLIs and design systems. | Apache-2.0 | Reference for design-workbench UX, BYOK agent routing, and composable design skills; keep external CLI execution behind LiMa allowlists. | LiMa Code, Main |
| `walkinglabs/learn-harness-engineering` | Multilingual harness-engineering learning material. | No standard license in API metadata | Documentation/reference input for LiMa harness engineering vocabulary and onboarding; do not copy content without license review. | Main, LiMa Code |
| `mvanhorn/last30days-skill` | AI agent skill that searches Reddit, X, YouTube, HN, Polymarket, GitHub, and web sources, then ranks by engagement and synthesizes a grounded brief. | MIT | Reference for time-bounded research skills, source scoring, social-signal synthesis, and BYO-key/source-session boundaries. | Main, LiMa Code |
| `flipbook.page` | Infinite visual browser generated on demand. | Website, no repo/license reviewed | Concept-only reference for visual exploration UI and generated artifact browsing. | Main, LiMa Code |
| Feishu wiki: `2026 企业级AI编程实践手册` | Enterprise AI programming methodology covering context engineering, skills, agentic coding, MCP, rules/specs, and organization/process practices. | Publicly reachable page, no reuse license observed | Background methodology reference only. Paraphrase with attribution; do not copy structure or text wholesale unless reuse rights are confirmed. | Main, LiMa Code |
| `sansan0/TrendRadar` | AI-driven trend/public-opinion monitor with RSS, multi-platform aggregation, AI briefs, MCP server, and WeChat/Feishu/DingTalk/Telegram/email/ntfy/Bark/Slack/Webhook-style alerts. | GPL-3.0 | Concept-only unless isolated; borrow trend monitor shape, source taxonomy, alert routing, and AI brief workflow. | Main |
| `calesthio/OpenMontage` | Agentic video production system with pipelines, tools, provider docs, and agent guide. | AGPL-3.0 | Concept-only for media-generation workflow shape, artifact pipeline staging, and skill/tool catalog design; no code copy. | Main, LiMa Code |
| `OpenBMB/VoxCPM` | Tokenizer-free multilingual TTS with voice design, controllable voice cloning, streaming, and 48kHz output. | Apache-2.0 | Candidate reference for later LiMa voice confirmation/companion speech, but voice cloning requires consent, model/weight review, GPU/latency budget, and audio retention policy. | Main, esp32S_XYZ |
| `firecrawl/open-lovable` | Chat-to-React app builder that clones/recreates websites using Firecrawl and sandbox providers. | MIT | Reference for LiMa Code website-to-app/design reconstruction workflow; keep scraping, API keys, sandbox execution, and generated code behind opt-in review/tests. | LiMa Code, Main |
| `alchaincyf/hermes-agent-orange-book` | Practical guide to Hermes Agent, covering learning loop, three-layer memory, Skills, tools, and multi-agent scenarios. | CC BY-NC-SA 4.0 content | Concept-only/non-commercial guide reference for self-improving agent boundaries, memory layering, and skill evolution vocabulary. | Main, LiMa Code |
| `repowise-dev/claude-code-prompts` | Independently authored prompt templates for coding agents: system, tool, agent, memory, and coordinator prompts. | MIT | Reference for LiMa Code prompt-contract shape, tool-specific instructions, verification prompts, memory prompts, and delegation boundaries. | LiMa Code, Main |
| `claude.com/resources/use-cases` | Official Claude use-case library organized around practical personal, professional, and cowork workflows. | Website/service | Product taxonomy reference for LiMa examples, onboarding, workflow templates, and user-facing scenario grouping; no scraping or copy without review. | Main, LiMa Code |
| `https://mirrors.tuna.tsinghua.edu.cn/` | Tsinghua Open Source Mirror for common package ecosystems and release artifacts. | Website/service | Operational reference for China/VPS bootstrap reliability and documented mirror fallbacks; not a code dependency. | Main, LiMa Code, esp32S_XYZ |
| `modelcontextprotocol/servers` | Official MCP reference implementations for Filesystem, Git, Memory, Sequential Thinking, Fetch, Time, and SDK examples. | Repository metadata has no single SPDX assertion; individual packages require review | Use as protocol/API reference only. The README states these are educational reference implementations, not production-ready services. | Main, LiMa Code |
| Official MCP Registry | Published MCP server registry. | Website/service | Source for candidate discovery only; every server still needs LiMa-specific permission, secret, network, and audit review. | Main, LiMa Code |
| `wong2/awesome-mcp-servers` | Curated community list of MCP servers. | MIT | Discovery input for the candidate catalog; do not install by default. | Main, LiMa Code |
| TurboMCP | Online MCP runtime reference. | Website/service, no license reviewed | Concept-only for hosted/online MCP experiments; no production use without account, data-flow, and security review. | Main |
| `akdeb/ElatoAI` | ESP32 realtime voice AI with secure WebSockets for toys, companions, and devices. | No standard license in API metadata | Already admitted as voice/device-companion reference; no runtime dependency. | esp32S_XYZ, Main |
| `NVIDIA/personaplex` | Realtime full-duplex speech-to-speech conversational model with text persona prompting and audio voice conditioning. | Code MIT; model weights require NVIDIA Open Model License review | Borrow realtime voice/persona architecture for later companion-device speech loops; do not adopt model weights without a separate license, GPU, safety, and privacy review. | Main, esp32S_XYZ |
| `anysearch-ai/anysearch-skill` | Unified realtime search skill for AI agents: web search, vertical search, batch search, and page extraction. | No standard license in API metadata | Borrow skill boundary and search-result evidence shape for LiMa research tasks; do not install until license/security review. | Main, LiMa Code |
| `TencentCloud/CubeSandbox` | Fast, concurrent, hardware-isolated sandbox service for AI agents, E2B-compatible. | No standard license in API metadata | Evaluate as external deployment component for worker isolation; do not vendor before review. | Main, LiMa Code |
| `browser-use/browser-harness` | Self-healing browser harness for LLM tasks. | MIT | Borrow browser verification pattern for online distributions and local UI tests. | Main, LiMa Code |
| `CloakHQ/CloakBrowser` | Browser automation/runtime package distributed through PyPI, npm, and Docker. | MIT | Evaluate as a controlled browser runtime candidate for LiMa UI/web verification, with anti-detection/ToS risks reviewed before use. | Main, LiMa Code |
| `hyperbrowserai/hyperbrowser-app-examples` | Production-style web apps built around browser automation, scraping, data extraction, and deployment patterns. | README says MIT; GitHub API returned no SPDX assertion during review | Reference for browser task app patterns and extraction UX. Keep API keys, scraping, target-site terms, privacy, and anti-abuse controls behind review; do not install by default. | Main, LiMa Code |
| `baoku.youdao.com` | Upload PDF/PPT/papers, AI summaries, PPT, mind maps, podcast, infographics, document QA. | Website, no repo/license reviewed | Product reference for document-to-knowledge workflows and report generation UX. | Main |
| `garrytan/gbrain` | Opinionated agent brain built around OpenClaw/Hermes style workflows. | MIT | Borrow agent brain packaging, role memory, and opinionated workflow ideas after review. | Main, LiMa Code |
| `garrytan/gstack` | Opinionated AI software-factory skill stack with planning, CEO/eng/design review, QA/browser testing, security review, release/deploy, guard/freeze/careful safety commands, cross-agent browser pairing, gbrain setup, and multi-host skill install paths. | MIT | Strong LiMa Code workflow reference for stage-gated build/review/test/ship, browser QA artifacts, safety guard commands, cross-model second opinion, memory sync, and skill packaging. Do not install wholesale or enable role sprawl by default. | LiMa Code, Main |
| `rowboatlabs/rowboat` | Open-source AI coworker with memory. | Apache-2.0 | Borrow coworker/session memory patterns and user-facing task continuity. | Main, LiMa Code |
| `xixu-me/awesome-persona-distill-skills` | Curated agent skills for persona, relationships, scenes, and methodology. | CC0-1.0 | Borrow skill taxonomy for persona/style modules and companion UX. | Main, LiMa Code |
| `addyosmani/agent-skills` | Production-grade engineering skills and slash-command workflows for AI coding agents. | MIT | Strong candidate for LiMa Code skill packaging, command lifecycle, and quality-gate vocabulary. | LiMa Code, Main |
| `wjn1996/HeavySkill` | Parallel reasoning plus sequential deliberation workflow/prompt for agentic harnesses. | No standard license found during raw scan | Concept-only until license is verified; borrow evaluation idea for difficult planning/review tasks, not default runtime. | Main, LiMa Code |
| `Lum1104/Understand-Anything` | Turns codebases, docs, and knowledge bases into interactive searchable knowledge graphs. | MIT | Strong candidate reference for LiMa-owned code/document graph UI and search workflows. | Main, LiMa Code |
| `tirth8205/code-review-graph` | Local code knowledge graph for lower-token reviews and coding tasks. | MIT | Strong candidate for LiMa code-context graph roadmap and review prefetch logic. | Main, LiMa Code |
| `zilliztech/claude-context` | MCP/extension semantic code search for Claude Code and other coding agents. | MIT | Strong reference for codebase indexing, semantic retrieval, and MCP packaging for LiMa Code. | LiMa Code, Main |
| `vercel-labs/open-agents` | Template for cloud agents. | MIT | Borrow cloud-agent project structure, deploy boundaries, and agent API ergonomics. | Main |
| `openai/symphony` | Engineering preview for isolated autonomous implementation runs with proof-of-work signals. | Apache-2.0 | Borrow work-run isolation, proof bundle, CI/PR review evidence, and board-driven orchestration ideas behind LiMa approval gates. | Main, LiMa Code |
| `xming521/WeClone` | AI twin from chat history and style fine-tuning. | AGPL-3.0 | Concept-only unless legally isolated; borrow privacy/style boundaries, not code. | Main |
| `safishamsi/graphify` | Queryable knowledge graph over code, schemas, docs, papers, media, and infra. | MIT | Strong candidate for unified graph index ideas across code/docs/infra. | Main, LiMa Code |
| `vectorize-io/hindsight` | Agent memory that learns. | MIT | Borrow memory learning/evaluation loop for typed memory and promotion gates. | Main |
| `companion-inc/feynman` | Open-source AI research agent. | MIT | Borrow research-session CLI shape and citation/evidence workflow. | Main, LiMa Code |
| `nextlevelbuilder/goclaw` | Go OpenClaw-style runtime with multi-tenant isolation, 5-layer security, native concurrency, and agent-team deployment positioning. | No standard license in API metadata | Concept-only for multi-tenant agent safety, concurrency, and isolation design until license is reviewed. | Main |
| `filiksyos/gitreverse` | Reverse engineer a repository into its original prompt. | No standard license in API metadata | Concept-only for repo-to-spec and migration-plan extraction. | Main, LiMa Code |
| `MervinPraison/PraisonAI` | Multi-agent workforce with memory, RAG, many LLMs, and execution loops. | MIT | Borrow orchestration patterns where they fit LiMa's gated autonomy model. | Main |
| `aiming-lab/AutoResearchClaw` | Autonomous and self-evolving research pipeline from idea to paper, with OpenClaw integration, HITL modes, ARC-Bench, anti-fabrication checks, and budget guardrails. | MIT | Borrow research-stage gating, HITL intervention modes, anti-hallucination claim verification, benchmark manifests, and budget controls. | Main, LiMa Code |
| `Gen-Verse/OpenClaw-RL` | Fully async RL loop for training personalized agents from natural-language feedback across terminal, GUI, SWE, and tool-call settings, with async serving, rollout, judge, and training components. | Apache-2.0 | Research reference for future feedback-to-training/eval loops. Keep offline until privacy, consent, eval, rollback, model storage, compute, and cost gates exist. | Main, LiMa Code |
| `Yeachan-Heo/oh-my-codex` | Codex hooks, agent teams, HUDs, and workflow extensions. | No standard license in API metadata | Concept-only for LiMa Code hooks, HUD, and local workflow ergonomics. | LiMa Code |
| `VoltAgent/awesome-codex-subagents` | Curated Codex-native `.toml` subagent collection across many development categories. | MIT | Reference for subagent metadata shape, categories, sandbox defaults, and explicit delegation; do not install broad role libraries by default. | LiMa Code, Main |
| `can1357/oh-my-pi` | IDE-wired AI coding agent with TypeScript/Rust packaging. | MIT | Borrow local IDE/worker UX, panel/status ergonomics, and command routing ideas for LiMa Code. | LiMa Code |
| `anomalyco/opencode` | Open-source AI coding agent with terminal UI, package-manager distribution, desktop beta, and broad localization. | MIT | Reference for LiMa Code packaging, terminal/desktop UX, installer channels, localization, and coding-agent workflow ergonomics. | LiMa Code |
| `2025Emma/vibe-coding-cn` | Chinese Vibe Coding guide/workstation with prompts, skills, multilingual docs, planning-driven workflow, and AI pair-programming methodology. | MIT | Reference for LiMa Code Chinese onboarding, prompt/skill catalog organization, planning-first workflow, and user education. | LiMa Code |
| `aattaran/deepclaude` | Anthropic-compatible Claude Code backend swap for cheaper DeepSeek/OpenRouter style models. | MIT | Reference for LiMa-compatible local/remote model proxy ergonomics; ensure it never bypasses LiMa key custody or backend admission gates. | LiMa Code, Main |
| `msitarzewski/agency-agents` | Large library of specialized agent roles and deliverables. | MIT | Borrow role taxonomy for gated sub-agent prompts and review personas. | Main, LiMa Code |
| `tsinghua-fib-lab/OmniScientist` | AI scientist ecosystem for open-ended scientific discovery. | MIT | Borrow scientific discovery loop for long-running research/evaluation tasks. | Main |
| `openai/openai-agents-python` | Python Agents SDK with agents, tools, handoffs, guardrails, sessions, tracing, human-in-the-loop, and sandbox agents. | MIT | Strong reference for LiMa agent APIs, guardrails, tracing, handoff semantics, and sandbox-agent boundaries; keep LiMa provider/key custody intact. | Main |
| `google/adk-python` | Code-first Python Agent Development Kit for building, evaluating, and deploying agents. | Apache-2.0 | Reference for eval/deploy separation, agent app structure, and workflow state boundaries. | Main |
| `lsdefine/GenericAgent` | Minimal self-evolving autonomous agent framework with compact tool loop and skill growth. | MIT | Borrow self-evolution and minimal-loop ideas only behind LiMa evaluation, mastery evidence, and manual promotion gates. | Main |
| `EvoMap/evolver` | GEP-powered self-evolving agent system with memory/skill/evolution assets. | GPL-3.0 | Concept-only due GPL; borrow gated evolution vocabulary and evidence discipline, not code. | Main |
| `microsoft/agent-governance-toolkit` | Agent governance specifications, policy, telemetry, and compliance toolkit. | MIT | Strong reference for LiMa agent risk classification, approval metadata, audit fields, and deployment policy docs. | Main, LiMa Code |
| `datawhalechina/vibe-vibe` | Chinese Vibe Coding education/tutorial project for non-programmers moving from idea to product. | No license file found in raw scan | Product/onboarding reference for LiMa Code docs and user education, not runtime code. | LiMa Code |
| `NVlabs/GR00T-WholeBodyControl` | Whole-body control training/evaluation/deployment stack for humanoid robot controllers. | Source Apache-2.0; model weights under NVIDIA Open Model License | Concept-only robotics control reference for future physical-device abstractions; do not mix with writing-machine firmware until hardware safety gates are separate. | Main, esp32S_XYZ |
| `kyutai-labs/pocket-tts` | CPU-friendly lightweight TTS package/model for local text-to-speech. | MIT-style license text in raw scan; model card still needs review | Strong candidate for later offline/local TTS experiments behind opt-in model, latency, and resource gates. | Main, esp32S_XYZ |
| `antoniolupetti/algebrica` | Structured mathematics knowledge base with Markdown/LaTeX/SVG and semantic JSON. | CC BY-NC 4.0 content license | Concept-only/non-commercial content reference for structured knowledge products and equation-rich document UX. | Main |
| `zai-org/GLM-OCR` | Multimodal OCR model for complex document understanding and layout recognition. | Apache-2.0 | Evaluate as OCR/document-understanding reference after document ingestion boundaries and model/API terms are reviewed. | Main |
| `simchowitzlabpublic/nano-world-model` | Minimal diffusion-forcing video world-model training/evaluation pipeline. | MIT | Research reference for future simulation/world-model experiments; not needed for current writing-machine control. | Main |
| `666ghj/MiroFish` | Universal swarm-intelligence/prediction simulation engine with many agents, personalities, long-term memory, behavioral logic, high-fidelity parallel digital-world framing, and prediction reports. | AGPL-3.0 | Concept-only for simulation, scenario exploration, and swarm/world-model vocabulary. Predictions must never drive finance, hardware, or production actions without evidence, HITL, and safety gates. | Main |
| `Nunchi-trade/agent-cli` | Autonomous trading CLI with agent skills, MCP server, APEX multi-slot orchestrator, Guard trailing stops, Radar/Pulse scanners, REFLECT review loop, HTTP/SSE surfaces, risk guardian, reconciliation, and testnet/mainnet split. | MIT | Borrow deterministic orchestrator, risk-state, reconciliation, reflection, MCP-surface, and scheduled review patterns only. Trading/finance execution remains blocked and must not be copied into LiMa product behavior. | Main, LiMa Code |
| `https://hermes-agent.nousresearch.com/` | Official Hermes Agent site describing server-resident autonomous agent behavior, persistent memory, auto-generated skills, scheduled automations, isolated subagents, sandbox backends, browser/web control, and multi-platform messaging. | Website claims open source and MIT; source repo/license not separately reviewed | Conceptual benchmark for long-running agents, scheduling, memory, sandboxing, and subagent delegation. Treat site license as unverified for code-level reuse. | Main, LiMa Code |

## Priority Candidates

### P0 - Safe To Plan Immediately

- Pyrefly optional type checks for selected Python runtime modules.
- LightRAG-style graph/vector retrieval, multimodal parsing boundary, and
  role-specific extraction/query/VLM separation.
- Sirchmunk-style raw-file/indexless search, evidence sampling, streaming logs,
  and self-evolving knowledge clusters behind LiMa-owned privacy and path
  allowlists.
- Code-review graph / graphify / GitNexus / Understand-Anything /
  claude-context-style code context graph, starting with existing
  `code_context` and `lima_mcp` boundaries.
- stash / hindsight memory taxonomy, mapped to LiMa's existing memory and
  promotion records.
- browser-harness pattern for local/online browser smoke verification.
- Hyperbrowser/gstack-style browser task artifacts for UI verification and
  extraction workflows, with scraping/API-key risks gated.
- Microsoft Agent Governance Toolkit metadata for risk class, allowed actions,
  approval requirement, and evidence refs.
- OpenAI Agents SDK / Google ADK concepts for guardrails, sessions, tracing,
  handoffs, human-in-loop, eval/deploy separation, and workflow state
  boundaries.
- mattpocock skills / learn-harness-engineering as skill and harness
  engineering references.
- claude-code-prompts as a prompt-contract and tool-instruction reference.
- gstack as a stage-gated LiMa Code workflow reference for plan/review/QA/
  security/ship and safety guard commands.
- CubeSandbox external-sandbox evaluation, without vendoring code.
- AnySearch-style opt-in search skill boundary for research tasks, using
  LiMa's redaction and source allowlist rules.
- last30days-style time-bounded social/source research, but only behind BYO
  keys, source-session privacy, attribution, and rate-limit rules.
- TUNA mirror documentation for deterministic installs on China/VPS networks.
- MCP access catalog design: foundation connectors first, stack connectors
  second, business/data/media connectors only when a task requires them.

### P1 - Useful After P0 Interfaces Exist

- open-agents, Symphony, PraisonAI, goclaw, agency-agents, oh-my-codex,
  oh-my-pi, OpenAI Agents SDK, Google ADK, GenericAgent, agent-skills,
  HeavySkill, Hermes Agent Orange Book, AutoResearchClaw,
  OpenClaw-RL, Hermes Agent official site, agent-cli,
  awesome-codex-subagents, and deepclaude as inputs to LiMa's gated
  multi-agent orchestration and LiMa Code worker UX.
- Warp, OpenCode, Open Design, Pascal Editor, ClaudePrism, open-lovable, and
  vibe-coding-cn as terminal, design, web-to-app, 3D/canvas, onboarding, and
  scientific-writing workspace UX references.
- Feynman, ml-intern, AutoResearchClaw, OmniScientist, Algebrica, Claude use
  cases, Feishu enterprise AI programming handbook, and GLM-OCR as research,
  use-case taxonomy, methodology, structured-knowledge, and OCR/document-loop
  references.
- HF Viewer as a model-inspection UX reference.
- TrendRadar as alert/trend-monitor reference, with GPL isolation.
- OpenMontage as AGPL concept-only media workflow reference.
- Official MCP Registry and community MCP lists as discovery inputs for a
  reviewed, least-privilege connector catalog.
- CloakBrowser as an isolated browser-runtime candidate only after terms,
  privacy, and anti-abuse review.

### P2 - Product And Companion Later

- ElatoAI for voice/companion device work after writing-machine direct control.
- PersonaPlex for realtime speech-to-speech persona and voice-conditioning
  research after LiMa has explicit privacy, safety, and compute gates.
- pocket-tts for local/offline TTS experiments after voice-license, consent,
  CPU/latency, and retention reviews.
- VoxCPM for multilingual TTS, voice design, and controllable cloning research
  after consent, voice-license, GPU/latency, privacy, and retention gates.
- GLM-OCR for camera/document perception after file-ingestion privacy and
  hardware evidence gates.
- GR00T-WholeBodyControl and nano-world-model as robotics/simulation research
  references only, not writing-machine runtime dependencies.
- MiroFish as AGPL concept-only swarm/simulation reference; predictions cannot
  drive real actions without evidence and human review.
- OpenClaw-RL as a later feedback-to-training research reference, not a live
  self-training path.
- Evolver as a GPL concept-only self-evolution reference.
- Youdao Baoku for document-to-brief/PPT/mind-map product workflows.
- Flipbook for visual generated browsing.
- vibe-vibe for LiMa Code onboarding and user education material shape.
- Persona skill collections and WeClone-style AI twin ideas, with strict privacy
  and AGPL boundaries.
