# External Capability Adoption Roadmap

**Date:** 2026-05-24
**Status:** planned
**Scope:** convert the user-provided external reference list into staged,
reviewable LiMa Server, LiMa Code, and `esp32S_XYZ` improvements.

## Goal

Use the reference projects as a capability radar for LiMa without turning the
main repo into a dependency dump. Each borrowed idea must land through a small
LiMa-native interface, tests, documentation, and a clear license boundary.

The 2026-05-24 expansion added AnySearch Skill, oh-my-pi, Microsoft Agent
Governance Toolkit, vibe-vibe, CloakBrowser, GR00T-WholeBodyControl,
pocket-tts, OpenAI Symphony, Algebrica, GLM-OCR, nano-world-model,
agent-skills, HeavySkill, Understand-Anything, deepclaude, and claude-context
to the radar. Duplicate Pyrefly and PersonaPlex entries remain de-duplicated in
the source inventory.

Primary source inventory:

- `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`
- `docs/reference/HARDWARE_COMPANION_REFERENCES.md`

## Repository Targets

| Target | Role | External capability fit |
|---|---|---|
| Main LiMa repo | Model routing, memory, agent control plane, VPS surfaces, Device Gateway | Type checks, code graph, memory learning, agent orchestration, sandboxing, trend/research loops |
| `deepcode-cli` | Local coding worker, tool execution, MCP client, terminal UX | Code graph context, hooks, HUD/workflow UX, browser harness, repo-to-spec extraction |
| `esp32S_XYZ` | Hardware product, firmware, fake devices, schemas, U8/U1 control | ElatoAI-style voice/device session ideas, display/companion route after writing-machine gates |

## Adoption Principles

1. Concept first, code later.
2. No direct copy from repositories with no reviewed license, GPL, or AGPL.
3. Every adopted capability needs a LiMa-owned API, tests, and rollback path.
4. Keep the first implementation slices small and orthogonal.
5. Do not let research/agent frameworks bypass LiMa's provider key custody,
   device safety, VPS governance, or human approval gates.

## Phase 0 - Reference Governance

Tasks:

- Keep a source table with URL, observed capability, license signal, target
  repo, and adoption status.
- Add a per-reference review checklist before any clone becomes a dependency.
- Define statuses: `concept`, `evaluating`, `adapter-planned`, `implemented`,
  `rejected`, `quarantined`.

Exit criteria:

- External capability radar is committed.
- Documentation status and durable memory point to it.
- No runtime dependency is added.

## Phase 1 - Code Quality And Code Intelligence

References:

- Pyrefly
- code-review-graph
- graphify
- GitNexus
- gitreverse
- Understand-Anything
- claude-context

Main repo plan:

- Add an optional Pyrefly lane for a narrow set of stable Python modules first:
  `backends.py`, `key_pool.py`, `http_caller.py`, `routes/*.py`,
  `code_context/*.py`, and future `device_gateway/*.py`.
- Extend the current `code_context` layer with a graph-index interface before
  choosing any backend implementation.
- Add repo-to-spec extraction as a read-only tool for onboarding external repos
  and product submodules.
- Evaluate semantic/MCP code-search packaging from claude-context and
  interactive graph UX from Understand-Anything against LiMa's existing
  `code_context` boundaries.

LiMa Code plan:

- Surface graph-index snippets to local coding sessions.
- Add a review-context prefetch command that explains why each file was pulled.

Exit criteria:

- Focused type-check command exists and can be run without breaking the whole
  monorepo.
- Graph-index interface has fixture tests.
- No external graph package is required to pass core tests.

## Phase 2 - Memory And Learning

References:

- stash
- hindsight
- gbrain
- rowboat

Main repo plan:

- Normalize LiMa memory into episode, fact, working-context, promotion, and
  evidence records.
- Add memory promotion scoring that separates raw observations from accepted
  operational knowledge.
- Expose a small internal memory query API for routing, worker preflight, and
  research tasks.

LiMa Code plan:

- Store worker-relevant session memory without leaking secrets or provider
  credentials.
- Distinguish user preferences, project facts, and temporary task context.

Exit criteria:

- Memory records are typed and queryable.
- Promotion and rejection decisions are auditable.
- Tests prove that secret-like values are not promoted.

## Phase 3 - Agent Orchestration And Work Queues

References:

- open-agents
- OpenAI Symphony
- PraisonAI
- agency-agents
- goclaw
- oh-my-codex
- oh-my-pi
- clawsweeper
- agent-skills
- HeavySkill
- deepclaude

Main repo plan:

- Keep LiMa's existing gated autonomy model as the control plane.
- Add role templates only as data, not as unrestricted autonomous workers.
- Add issue/plan hygiene checks that recommend stale-item closure, never close
  automatically without a recorded approval rule.
- Borrow Symphony-style isolated work runs and proof bundles only behind LiMa's
  existing approval, CI, review, audit, and push gates.
- Borrow agent-skills / HeavySkill only as opt-in workflow prompts or eval
  patterns; do not make them hidden default reasoning paths.
- Treat deepclaude-style provider swapping as a UX reference only; LiMa must
  keep provider key custody, backend admission, and routing policy in the main
  backend registry.

LiMa Code plan:

- Evaluate hook/HUD patterns for local worker status, command safety, and
  review checkpoints.
- Add role-specific prompts only when they map to real project tasks.

Exit criteria:

- Agent roles have ownership boundaries and allowed actions.
- Work queue items have status, evidence, and rollback notes.
- No agent can deploy, push, or touch hardware without explicit gate metadata.

## Phase 4 - Secure Execution And Browser Verification

References:

- CubeSandbox
- browser-harness
- Microsoft Agent Governance Toolkit
- CloakBrowser

Main repo plan:

- Evaluate CubeSandbox as an optional external sandbox provider for risky
  worker execution and untrusted repo experiments.
- Add a browser-harness-inspired verification layer for official website, open
  platform, chat UI, and local web tools.
- Add governance metadata inspired by Microsoft Agent Governance Toolkit:
  risk class, allowed actions, human-approval requirement, evidence refs, and
  rollback owner for each autonomous work item.
- Evaluate CloakBrowser only in isolated browser-verification experiments.
  Anti-detection or scraping-like capabilities require terms-of-service,
  privacy, and target-site policy review before use.

LiMa Code plan:

- Route dangerous local execution through explicit safety checks.
- Record browser task screenshots/logs as artifacts when a UI claim is made.

Exit criteria:

- Sandbox provider remains optional and disabled by default.
- Browser verification can run against local and VPS surfaces.
- Verification artifacts are linked from progress records.

## Phase 5 - Research, Trend, And Knowledge Products

References:

- ml-intern
- OmniScientist
- Feynman
- AnySearch Skill
- TrendRadar
- Youdao Baoku
- Flipbook
- Algebrica
- GLM-OCR

Main repo plan:

- Add a research-task pipeline that records query, sources, summary, evidence,
  and follow-up tasks.
- Add trend-monitor adapters behind provider and source allowlists.
- Add document-to-brief/PPT/mind-map planning only after local document
  ingestion boundaries are reviewed.
- Use AnySearch as a search-skill boundary reference for opt-in web search,
  batch search, vertical search, and full-page extraction with redaction.
- Use GLM-OCR as a document/OCR provider reference after file-ingestion privacy,
  model/API terms, and resource budgets are reviewed.
- Treat Algebrica as a non-commercial structured-knowledge/content reference,
  not as copyable training or runtime content.

LiMa Code plan:

- Provide research summaries to coding sessions as structured findings.
- Keep generated visual browsing as an artifact viewer, not as a source of
  truth without citations.

Exit criteria:

- Research outputs cite sources and record retrieval dates.
- Trend monitors are opt-in and rate-limited.
- Generated reports do not expose private files by default.

## Phase 6 - Persona, Style, Voice, Display, And Hardware Companions

References:

- awesome-persona-distill-skills
- WeClone
- ElatoAI
- PersonaPlex
- pocket-tts
- Feynman
- Flipbook
- Youdao Baoku
- GR00T-WholeBodyControl
- nano-world-model

Main repo plan:

- Add persona/style records only with explicit user consent and privacy
  boundaries.
- Keep AI-twin ideas concept-only because AGPL/privacy risks require separate
  review.
- Evaluate realtime speech-to-speech persona models only behind explicit
  model-license, GPU/latency, privacy, safety, and opt-in recording gates.
- Evaluate pocket-tts as a local/offline TTS provider candidate for voice
  confirmation after latency, CPU, voice-license, and consent gates pass.
- Keep GR00T-WholeBodyControl and nano-world-model in the research/simulation
  lane. They may inspire robotics safety layering, simulation, and planning
  gates, but they must not bypass the writing-machine `run_path` allowlist or
  real-hardware smoke gates.
- Extend the Device Gateway only after writing-machine direct control passes
  fake U8 and real U8/U1 gates.

`esp32S_XYZ` plan:

- Finish writing-machine control first.
- Add voice, display, OCR, and camera/device-perception classes as separate
  protocol families:
  `audio_stream`, `speech`, `display_task`, `ui_state`, `ocr_result`,
  `vision_observation`.
- Keep realtime persona speech as a backend model capability, not as firmware
  logic.
- Keep motion, voice, and display on separate allowlists.

Exit criteria:

- Writing-machine direct mode is verified before companion devices.
- Each new hardware class has schema, fake-device tests, and safety rules.
- No persona training data is stored without an explicit retention policy.
- No realtime persona model is enabled without a reviewed model license,
  opt-in consent, and resource budget.

## First Implementation Slice

Recommended first slice after this plan is accepted:

1. Add a focused Pyrefly evaluation command and record current failures as
   non-blocking baseline.
2. Add a LiMa-owned `code_context.graph_index` interface and tests with an
   in-memory implementation.
3. Add typed memory record categories inspired by stash/hindsight, with secret
   hygiene tests.
4. Add browser verification plan entries for VPS website, open platform, and
   chat UI.
5. Add governance metadata fields to agent tasks before expanding autonomous
   work loops.
6. Defer agent-runtime and hardware-companion implementation until these
   foundations are stable.

## Verification

Documentation-only changes:

```powershell
cd D:\GIT
git diff --check -- docs\reference\EXTERNAL_CAPABILITY_RADAR_2026-05-24.md docs\superpowers\plans\2026-05-24-external-capability-adoption-roadmap.md
rg -n "External Capability|Pyrefly|CubeSandbox|ElatoAI|WeClone|Graph" docs
```

Implementation phases must add focused tests for the touched module and avoid
requiring network access in default CI unless the phase explicitly introduces a
network-gated smoke.
