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
| Static analysis and code intelligence | Pyrefly, GitNexus, code-review-graph, graphify, gitreverse | Main repo quality gates, LiMa Code context, review and repository understanding |
| Memory and agent knowledge | stash, hindsight, gbrain, rowboat | Durable memory, episode/fact separation, learning loops, agent state |
| Agent orchestration and workflow | open-agents, PraisonAI, agency-agents, goclaw, oh-my-codex, clawsweeper | Controlled multi-agent work, hooks, review queues, issue/PR triage |
| Secure execution and browser work | CubeSandbox, browser-harness | Safer worker execution, browser task verification, VPS/local isolation |
| Research, trends, and knowledge products | ml-intern, OmniScientist, Feynman, TrendRadar, Youdao Baoku, Flipbook | Research agents, trend monitors, document-to-brief/PPT/mind-map, visual browsing |
| Persona, style, and companion behavior | awesome-persona-distill-skills, WeClone, Feynman, ElatoAI, PersonaPlex | User style modeling, companion UX, voice/display persona boundaries |
| Hardware and device companions | ElatoAI, PersonaPlex, ESP32 display references already tracked separately | Device Gateway voice/display/companion expansion after writing-machine gates |

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
| `TencentCloud/CubeSandbox` | Fast, concurrent, hardware-isolated sandbox service for AI agents, E2B-compatible. | No standard license in API metadata | Evaluate as external deployment component for worker isolation; do not vendor before review. | Main, LiMa Code |
| `browser-use/browser-harness` | Self-healing browser harness for LLM tasks. | MIT | Borrow browser verification pattern for online distributions and local UI tests. | Main, LiMa Code |
| `baoku.youdao.com` | Upload PDF/PPT/papers, AI summaries, PPT, mind maps, podcast, infographics, document QA. | Website, no repo/license reviewed | Product reference for document-to-knowledge workflows and report generation UX. | Main |
| `garrytan/gbrain` | Opinionated agent brain built around OpenClaw/Hermes style workflows. | MIT | Borrow agent brain packaging, role memory, and opinionated workflow ideas after review. | Main, LiMa Code |
| `rowboatlabs/rowboat` | Open-source AI coworker with memory. | Apache-2.0 | Borrow coworker/session memory patterns and user-facing task continuity. | Main, LiMa Code |
| `xixu-me/awesome-persona-distill-skills` | Curated agent skills for persona, relationships, scenes, and methodology. | CC0-1.0 | Borrow skill taxonomy for persona/style modules and companion UX. | Main, LiMa Code |
| `tirth8205/code-review-graph` | Local code knowledge graph for lower-token reviews and coding tasks. | MIT | Strong candidate for LiMa code-context graph roadmap and review prefetch logic. | Main, LiMa Code |
| `vercel-labs/open-agents` | Template for cloud agents. | MIT | Borrow cloud-agent project structure, deploy boundaries, and agent API ergonomics. | Main |
| `xming521/WeClone` | AI twin from chat history and style fine-tuning. | AGPL-3.0 | Concept-only unless legally isolated; borrow privacy/style boundaries, not code. | Main |
| `safishamsi/graphify` | Queryable knowledge graph over code, schemas, docs, papers, media, and infra. | MIT | Strong candidate for unified graph index ideas across code/docs/infra. | Main, LiMa Code |
| `vectorize-io/hindsight` | Agent memory that learns. | MIT | Borrow memory learning/evaluation loop for typed memory and promotion gates. | Main |
| `companion-inc/feynman` | Open-source AI research agent. | MIT | Borrow research-session CLI shape and citation/evidence workflow. | Main, LiMa Code |
| `nextlevelbuilder/goclaw` | Go OpenClaw-style runtime with multi-tenant isolation, layered security, concurrency. | No standard license in API metadata | Concept-only for multi-tenant agent safety and concurrency design. | Main |
| `filiksyos/gitreverse` | Reverse engineer a repository into its original prompt. | No standard license in API metadata | Concept-only for repo-to-spec and migration-plan extraction. | Main, LiMa Code |
| `MervinPraison/PraisonAI` | Multi-agent workforce with memory, RAG, many LLMs, and execution loops. | MIT | Borrow orchestration patterns where they fit LiMa's gated autonomy model. | Main |
| `Yeachan-Heo/oh-my-codex` | Codex hooks, agent teams, HUDs, and workflow extensions. | No standard license in API metadata | Concept-only for LiMa Code hooks, HUD, and local workflow ergonomics. | LiMa Code |
| `msitarzewski/agency-agents` | Large library of specialized agent roles and deliverables. | MIT | Borrow role taxonomy for gated sub-agent prompts and review personas. | Main, LiMa Code |
| `tsinghua-fib-lab/OmniScientist` | AI scientist ecosystem for open-ended scientific discovery. | MIT | Borrow scientific discovery loop for long-running research/evaluation tasks. | Main |

## Priority Candidates

### P0 - Safe To Plan Immediately

- Pyrefly optional type checks for selected Python runtime modules.
- Code-review graph / graphify / GitNexus-style code context graph, starting
  with existing `code_context` and `lima_mcp` boundaries.
- stash / hindsight memory taxonomy, mapped to LiMa's existing memory and
  promotion records.
- browser-harness pattern for local/online browser smoke verification.
- CubeSandbox external-sandbox evaluation, without vendoring code.

### P1 - Useful After P0 Interfaces Exist

- open-agents, PraisonAI, goclaw, agency-agents, and oh-my-codex as inputs to
  LiMa's gated multi-agent orchestration and LiMa Code worker UX.
- Feynman, ml-intern, and OmniScientist as research-loop references.
- TrendRadar as alert/trend-monitor reference, with GPL isolation.

### P2 - Product And Companion Later

- ElatoAI for voice/companion device work after writing-machine direct control.
- PersonaPlex for realtime speech-to-speech persona and voice-conditioning
  research after LiMa has explicit privacy, safety, and compute gates.
- Youdao Baoku for document-to-brief/PPT/mind-map product workflows.
- Flipbook for visual generated browsing.
- Persona skill collections and WeClone-style AI twin ideas, with strict privacy
  and AGPL boundaries.
