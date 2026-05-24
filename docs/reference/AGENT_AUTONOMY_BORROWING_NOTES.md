# Agent Autonomy Borrowing Notes

## Borrowed Concepts

- OpenAI Agents-style guardrails, tracing, and explicit handoff boundaries.
- OpenAI Agents SDK-style sessions, tracing, handoffs, guardrails,
  human-in-loop, and sandbox-agent boundaries.
- Google ADK-style separation between workflow/task state, evaluation,
  deployment, and the production router hot path.
- GenericAgent-style layered memory and candidate skill extraction after verified task success.
- EvoMap-style gated promotion: candidates remain inactive until evaluation, manual approval, and evidence exist.
- Agency-agents-style role separation: planner, coder, reviewer, tester, and memory/evolution responsibilities stay distinct.
- Microsoft Agent Governance Toolkit-style governance metadata: risk class,
  allowed actions, policy trace, human approval requirement, and audit
  evidence.
- OpenAI Symphony-style isolated implementation runs and proof bundles, kept
  behind LiMa's existing Server/Worker approval gates.
- agent-skills and HeavySkill-style explicit workflow skills, quality gates,
  and opt-in deep reasoning for hard tasks.
- mattpocock skills and learn-harness-engineering-style small, composable,
  user-controlled engineering skills and harness practices.
- repowise claude-code-prompts-style prompt contracts, tool-specific
  instructions, verification prompts, memory prompts, and delegation boundaries.
- Hermes Agent Orange Book-style learning loop, memory layering, skill
  creation, and self-improvement vocabulary as a non-commercial concept
  reference.
- goclaw-style multi-tenant isolation, layered security, native concurrency,
  and agent-team deployment boundaries as concept inputs.
- awesome-codex-subagents-style Codex-native `.toml` metadata, category
  organization, sandbox defaults, and explicit delegation prompts.
- AutoResearchClaw-style staged research pipeline with HITL modes,
  anti-fabrication claim checks, benchmark manifests, budget guardrails, and
  cross-run learning.
- OpenClaw-RL-style separation of asynchronous serving, rollout, judging, and
  training loops, used only as a future offline evaluation/training reference.
- Hermes Agent official-site capability benchmark: server-resident agent,
  persistent memory, generated skills, scheduled automations, isolated
  subagents, sandbox backends, browser/web control, and messaging surfaces.
- gstack-style stage-gated software factory: product interrogation, plan
  review, engineering review, design review, QA/browser testing, security
  audit, release/deploy checks, safety guard commands, cross-model review, and
  memory sync.
- Nunchi agent-cli-style deterministic orchestration with explicit risk states,
  reconciliation, scheduled reflection, MCP tool surfaces, and HTTP/SSE
  observability, with trading behavior excluded.
- Google Cloud generative-ai sample structure for Gemini/Agent Platform,
  Agent Search, RAG/grounding, function/tool calling, vision, and audio demos.
- Agent-Reach-style channel scaffolding and doctor checks for practical
  internet reach, with each upstream tool kept replaceable and gated.
- cc-connect-style messaging bridge, web admin, lifecycle hooks, skill page,
  provider management, mobile chat surfaces, and cron UX as distribution
  references.
- last30days-style time-bounded research skills that rank sources by observed
  engagement and synthesize grounded briefs.
- oh-my-pi-style local IDE/tool harness ergonomics for LiMa Code.
- deepclaude-style backend proxy ergonomics as a UX reference only, never as a
  bypass around LiMa provider admission or key custody.
- Sub-Agent versus Agent Team coordination boundary: default to isolated
  sub-agents for cleanly separable research, review, test, and verification
  work; upgrade to an Agent Team only when the task needs shared state, real-time
  communication, and long-lived coordination.
- MCP connector taxonomy from the user-provided guide: Skills define methods;
  MCP servers grant authority to act. LiMa uses that distinction to keep
  permissions, credentials, and audit outside prompt-only skill packs.
- Feishu enterprise AI programming methodology: context engineering, specs,
  rules, skills, MCP, and process discipline as background concepts only.
- Sequential Thinking MCP-style explicit reasoning flows for difficult tasks,
  only when the workflow is visible and auditable.
- Memory MCP-style knowledge graph memory as a reference shape; LiMa's active
  memory remains typed, evidence-gated, and secret-redacted.
- Google MCP-style cataloging of managed remote MCP servers and open-source MCP
  servers, with Cloud Run hosting as a deployment reference.
- RuVector-style adaptive vector/graph memory and audit/branching vocabulary,
  but only after benchmarked retrieval quality and drift behavior.

## Coordination Rule

- Start with one owner agent when tasks share deep context.
- Use sub-agents like isolated function calls: each receives a bounded context,
  independent tools, and returns a clean result to the owner.
- Do not split by generic roles such as planner, developer, and tester when the
  handoff would lose the intent, tradeoffs, or implementation context.
- Use Agent Teams only when agents must communicate during execution, react to
  each other's changes, or coordinate over a shared task/event layer.
- Before creating an Agent Team, require an explicit shared-state model,
  ownership map, audit trail, conflict policy, and stop/approval gate.

## Rejected Concepts

- Unbounded shell access.
- Fully autonomous production mutation.
- External worker pools.
- Dynamic package installation as a default behavior.
- Large persona-agent libraries before trace and approval gates are mature.
- Hidden autonomous model/provider swaps outside LiMa's routing registry.
- Skill packs that can change tool permissions, deployment behavior, or
  hardware access without explicit review.
- MCP servers enabled by hype list, broad default install, or generic "30
  must-have" bundles instead of task need, owner, least privilege, and audit.
- Hidden Sequential Thinking traces as a default chain-of-thought mechanism.
- External Memory MCP stores as the source of truth without LiMa promotion,
  retention, and redaction gates.
- Copying non-commercial Hermes Orange Book content into LiMa runtime prompts
  or product docs without a separate license review.
- Enabling goclaw-style agent teams before LiMa has shared-state, isolation,
  conflict, audit, and stop/approval policies.
- Installing broad subagent catalogs by default instead of selecting bounded,
  task-specific subagents with clear ownership.
- Letting autonomous research systems generate papers, claims, citations, or
  public artifacts without human review, evidence checks, budget controls, and
  rollback.
- Letting RL/self-training systems consume private chats, task transcripts,
  browser sessions, or hardware traces without consent, privacy review, eval
  baselines, rollback, model-storage policy, and cost limits.
- Searching social platforms through user sessions or API keys without consent,
  platform-term review, privacy boundaries, and attribution rules.
- Letting browser automation examples become default scraping/extraction tools
  without target-site terms, rate-limit, privacy, credential, and anti-abuse
  review.
- Enabling Google Cloud, Workspace, database, Maps, DevTools, or security MCP
  connectors without least-privilege IAM, billing/cost caps, data-residency
  review, audit, and rollback owner.
- Installing Agent-Reach-style social/cookie/proxy tools without explicit user
  consent, account isolation, platform-term review, and redacted credential
  storage.
- Allowing cc-connect-style messaging bridges to send outbound messages,
  execute shell/admin commands, or run cron jobs without approval and audit.
- Using bluebox-style closed-API or website reverse-engineering on targets
  without a documented target policy and anti-abuse review.
- Treating RuVector-style self-learning memory as authoritative before
  benchmarks, regression tests, and drift monitors prove it improves LiMa.
- Copying Feishu-hosted methodology text or structure without reuse rights.
- Copying AGPL swarm/simulation systems or allowing prediction reports to
  trigger real production, finance, messaging, or hardware actions.
- Financial/trading automation inside LiMa runtime. Nunchi agent-cli is an
  architecture reference only.
- Direct dependency on GPL self-evolution systems; use only concept notes unless
  a separate legal review approves isolation.
- Multi-agent role sprawl where coordination overhead is larger than the task.
- Agent Teams without a shared task layer, event log, conflict policy, and
  explicit owner.

## LiMa Implementation

- Server task APIs and LiMa Code bounded worker loops provide the current agent workbench.
- Current default orchestration mode is owner-agent plus isolated sub-agents.
- Candidate skills are suggestion-only until manually promoted.
- Promotion now requires mastery evidence references in addition to evaluation and manual approval.
- Production deploys, VPS operations, GitHub pushes, credential changes, and destructive commands remain approval-gated.

## License Boundary

These references are used for architecture concepts only. Do not vendor or copy source code from reference projects unless a separate license review explicitly permits it.
