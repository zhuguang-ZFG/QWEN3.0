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
| Static analysis and code intelligence | Pyrefly, GitNexus, code-review-graph, graphify, gitreverse, Understand-Anything, claude-context | Main repo quality gates, LiMa Code context, review and repository understanding |
| Memory and agent knowledge | stash, hindsight, gbrain, rowboat | Durable memory, episode/fact separation, learning loops, agent state |
| Agent orchestration, skills, and workflow | open-agents, Symphony, PraisonAI, agency-agents, goclaw, oh-my-codex, oh-my-pi, clawsweeper, agent-skills, HeavySkill, vibe-vibe | Controlled multi-agent work, hooks, review queues, issue/PR triage, skill packaging, work-run isolation |
| Governance, secure execution, and browser work | Microsoft Agent Governance Toolkit, CubeSandbox, browser-harness, CloakBrowser | Safer worker execution, browser task verification, VPS/local isolation, governance policy |
| Search, research, trends, and knowledge products | AnySearch Skill, ml-intern, OmniScientist, Feynman, TrendRadar, Youdao Baoku, Flipbook, Algebrica, GLM-OCR | Research agents, trend monitors, search extraction, document-to-brief/PPT/mind-map, OCR, visual browsing |
| Persona, style, and companion behavior | awesome-persona-distill-skills, WeClone, Feynman, ElatoAI, PersonaPlex, pocket-tts | User style modeling, companion UX, voice/display persona boundaries |
| Hardware, robotics, and world models | ElatoAI, PersonaPlex, oh-my-pi, GR00T-WholeBodyControl, pocket-tts, nano-world-model, ESP32 display references already tracked separately | Device Gateway voice/display/companion expansion after writing-machine gates |

## Source Evaluation

| Source | Observed capability | License signal | Borrow for LiMa | Target repo |
|---|---|---|---|---|
| `facebook/pyrefly` | Fast Python type checker and language server with gradual adoption tools. | MIT | Add optional focused type-check lane for stable Python modules before expanding to the whole repo. | Main, LiMa Code |
| `huggingface/ml-intern` | ML engineering agent that researches papers/docs/datasets and ships ML code. | Apache-2.0 | Borrow research-to-implementation loop for model evaluation, benchmark, and ML adapter tasks. | Main |
| `abhigyanpatwari/GitNexus` | Browser-side code knowledge graph and Graph RAG exploration. | No standard license in API metadata | Concept-only reference for local repository graph browsing and zero-server code exploration. | Main, LiMa Code |
| `alash3al/stash` | Persistent agent memory with episodes, facts, working context, Postgres, and MCP. | Apache-2.0 | Borrow memory taxonomy and MCP memory interface ideas for LiMa memory storage. | Main, LiMa Code |
| `openclaw/clawsweeper` | Scheduled issue/PR close recommendations. | MIT | Add future GitHub hygiene job for stale plans, issues, PRs, and close candidates. | Main |
| `flipbook.page` | Infinite visual browser generated on demand. | Website, no repo/license reviewed | Concept-only reference for visual exploration UI and generated artifact browsing. | Main, LiMa Code |
| `sansan0/TrendRadar` | AI-driven trend/public-opinion monitor with RSS, platform aggregation, alerts, and MCP. | GPL-3.0 | Concept-only unless isolated; borrow trend monitor shape and alert taxonomy. | Main |
| `akdeb/ElatoAI` | ESP32 realtime voice AI with secure WebSockets for toys, companions, and devices. | No standard license in API metadata | Already admitted as voice/device-companion reference; no runtime dependency. | esp32S_XYZ, Main |
| `NVIDIA/personaplex` | Realtime full-duplex speech-to-speech conversational model with text persona prompting and audio voice conditioning. | Code MIT; model weights require NVIDIA Open Model License review | Borrow realtime voice/persona architecture for later companion-device speech loops; do not adopt model weights without a separate license, GPU, safety, and privacy review. | Main, esp32S_XYZ |
| `anysearch-ai/anysearch-skill` | Unified realtime search skill for AI agents: web search, vertical search, batch search, and page extraction. | No standard license in API metadata | Borrow skill boundary and search-result evidence shape for LiMa research tasks; do not install until license/security review. | Main, LiMa Code |
| `TencentCloud/CubeSandbox` | Fast, concurrent, hardware-isolated sandbox service for AI agents, E2B-compatible. | No standard license in API metadata | Evaluate as external deployment component for worker isolation; do not vendor before review. | Main, LiMa Code |
| `browser-use/browser-harness` | Self-healing browser harness for LLM tasks. | MIT | Borrow browser verification pattern for online distributions and local UI tests. | Main, LiMa Code |
| `CloakHQ/CloakBrowser` | Browser automation/runtime package distributed through PyPI, npm, and Docker. | MIT | Evaluate as a controlled browser runtime candidate for LiMa UI/web verification, with anti-detection/ToS risks reviewed before use. | Main, LiMa Code |
| `baoku.youdao.com` | Upload PDF/PPT/papers, AI summaries, PPT, mind maps, podcast, infographics, document QA. | Website, no repo/license reviewed | Product reference for document-to-knowledge workflows and report generation UX. | Main |
| `garrytan/gbrain` | Opinionated agent brain built around OpenClaw/Hermes style workflows. | MIT | Borrow agent brain packaging, role memory, and opinionated workflow ideas after review. | Main, LiMa Code |
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
| `nextlevelbuilder/goclaw` | Go OpenClaw-style runtime with multi-tenant isolation, layered security, concurrency. | No standard license in API metadata | Concept-only for multi-tenant agent safety and concurrency design. | Main |
| `filiksyos/gitreverse` | Reverse engineer a repository into its original prompt. | No standard license in API metadata | Concept-only for repo-to-spec and migration-plan extraction. | Main, LiMa Code |
| `MervinPraison/PraisonAI` | Multi-agent workforce with memory, RAG, many LLMs, and execution loops. | MIT | Borrow orchestration patterns where they fit LiMa's gated autonomy model. | Main |
| `Yeachan-Heo/oh-my-codex` | Codex hooks, agent teams, HUDs, and workflow extensions. | No standard license in API metadata | Concept-only for LiMa Code hooks, HUD, and local workflow ergonomics. | LiMa Code |
| `can1357/oh-my-pi` | IDE-wired AI coding agent with TypeScript/Rust packaging. | MIT | Borrow local IDE/worker UX, panel/status ergonomics, and command routing ideas for LiMa Code. | LiMa Code |
| `aattaran/deepclaude` | Anthropic-compatible Claude Code backend swap for cheaper DeepSeek/OpenRouter style models. | MIT | Reference for LiMa-compatible local/remote model proxy ergonomics; ensure it never bypasses LiMa key custody or backend admission gates. | LiMa Code, Main |
| `msitarzewski/agency-agents` | Large library of specialized agent roles and deliverables. | MIT | Borrow role taxonomy for gated sub-agent prompts and review personas. | Main, LiMa Code |
| `tsinghua-fib-lab/OmniScientist` | AI scientist ecosystem for open-ended scientific discovery. | MIT | Borrow scientific discovery loop for long-running research/evaluation tasks. | Main |
| `microsoft/agent-governance-toolkit` | Agent governance specifications, policy, telemetry, and compliance toolkit. | MIT | Strong reference for LiMa agent risk classification, approval metadata, audit fields, and deployment policy docs. | Main, LiMa Code |
| `datawhalechina/vibe-vibe` | Chinese Vibe Coding education/tutorial project for non-programmers moving from idea to product. | No license file found in raw scan | Product/onboarding reference for LiMa Code docs and user education, not runtime code. | LiMa Code |
| `NVlabs/GR00T-WholeBodyControl` | Whole-body control training/evaluation/deployment stack for humanoid robot controllers. | Source Apache-2.0; model weights under NVIDIA Open Model License | Concept-only robotics control reference for future physical-device abstractions; do not mix with writing-machine firmware until hardware safety gates are separate. | Main, esp32S_XYZ |
| `kyutai-labs/pocket-tts` | CPU-friendly lightweight TTS package/model for local text-to-speech. | MIT-style license text in raw scan; model card still needs review | Strong candidate for later offline/local TTS experiments behind opt-in model, latency, and resource gates. | Main, esp32S_XYZ |
| `antoniolupetti/algebrica` | Structured mathematics knowledge base with Markdown/LaTeX/SVG and semantic JSON. | CC BY-NC 4.0 content license | Concept-only/non-commercial content reference for structured knowledge products and equation-rich document UX. | Main |
| `zai-org/GLM-OCR` | Multimodal OCR model for complex document understanding and layout recognition. | Apache-2.0 | Evaluate as OCR/document-understanding reference after document ingestion boundaries and model/API terms are reviewed. | Main |
| `simchowitzlabpublic/nano-world-model` | Minimal diffusion-forcing video world-model training/evaluation pipeline. | MIT | Research reference for future simulation/world-model experiments; not needed for current writing-machine control. | Main |

## Priority Candidates

### P0 - Safe To Plan Immediately

- Pyrefly optional type checks for selected Python runtime modules.
- Code-review graph / graphify / GitNexus / Understand-Anything /
  claude-context-style code context graph, starting with existing
  `code_context` and `lima_mcp` boundaries.
- stash / hindsight memory taxonomy, mapped to LiMa's existing memory and
  promotion records.
- browser-harness pattern for local/online browser smoke verification.
- Microsoft Agent Governance Toolkit metadata for risk class, allowed actions,
  approval requirement, and evidence refs.
- CubeSandbox external-sandbox evaluation, without vendoring code.
- AnySearch-style opt-in search skill boundary for research tasks, using
  LiMa's redaction and source allowlist rules.

### P1 - Useful After P0 Interfaces Exist

- open-agents, Symphony, PraisonAI, goclaw, agency-agents, oh-my-codex,
  oh-my-pi, agent-skills, HeavySkill, and deepclaude as inputs to LiMa's gated
  multi-agent orchestration and LiMa Code worker UX.
- Feynman, ml-intern, OmniScientist, Algebrica, and GLM-OCR as research,
  structured-knowledge, and OCR/document-loop references.
- TrendRadar as alert/trend-monitor reference, with GPL isolation.
- CloakBrowser as an isolated browser-runtime candidate only after terms,
  privacy, and anti-abuse review.

### P2 - Product And Companion Later

- ElatoAI for voice/companion device work after writing-machine direct control.
- PersonaPlex for realtime speech-to-speech persona and voice-conditioning
  research after LiMa has explicit privacy, safety, and compute gates.
- pocket-tts for local/offline TTS experiments after voice-license, consent,
  CPU/latency, and retention reviews.
- GLM-OCR for camera/document perception after file-ingestion privacy and
  hardware evidence gates.
- GR00T-WholeBodyControl and nano-world-model as robotics/simulation research
  references only, not writing-machine runtime dependencies.
- Youdao Baoku for document-to-brief/PPT/mind-map product workflows.
- Flipbook for visual generated browsing.
- vibe-vibe for LiMa Code onboarding and user education material shape.
- Persona skill collections and WeClone-style AI twin ideas, with strict privacy
  and AGPL boundaries.
