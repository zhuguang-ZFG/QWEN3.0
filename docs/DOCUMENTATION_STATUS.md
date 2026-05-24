# Documentation Status

> Updated: 2026-05-25
> Purpose: prevent old commercial-platform plans from being mistaken for the active LiMa direction.

## Current Source Of Truth

| Document | Status | Use |
|---|---|---|
| `STATUS.md` | Active | Short operational snapshot and public endpoint state. |
| `docs/LIMA_MEMORY.md` | Active | Durable memory for future coding-assistant sessions. |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | Active | Product direction and backend tier strategy. |
| `docs/FREE_MODEL_ROUTING_STATUS.md` | Active | SCNet/Kimi/free-model evidence and route policy. |
| `docs/LOCAL_PROXY_RUNTIME_STATUS.md` | Active | Windows proxy, LiMa API, and FRP closure. |
| `docs/FREE_WEB_AI_EXPANSION_PLAN.md` | Active record | Completed no-login web AI candidate, stability, and free routing efficiency plan. |
| `docs/FREE_WEB_AI_ADMISSION.md` | Active evidence | No-login web AI probe and admission decision record. |
| `docs/IDE_AGENT_VERIFICATION.md` | Active evidence | OpenAI-compatible, Anthropic-compatible, and real Claude Code CLI endpoint verification. |
| `docs/CLOUDFLARE_MODEL_INVENTORY.md` | Active | Cloudflare direct/Worker model inventory, routing policy, and adapter boundaries. |
| `docs/CLOUDFLARE_WORKER_QUICK_EVAL.md` | Active evidence | Worker quick coding eval for `cfai_qwen_coder`, `cfai_deepseek_r1`, and `cfai_mistral`. |
| `docs/EXECUTION_PLAN.md` | Active | Current phase tracker for documentation/GitHub snapshot and next implementation order. |
| `docs/REFERENCE_PROJECT_EVALUATION.md` | Active | Current evaluation of OpenRAG, Google Cloud always-on-memory-agent, TechSpar, and autonomy references against LiMa's real code state. |
| `docs/ONLINE_DISTRIBUTIONS.md` | Active | Source of truth for VPS-hosted official website, open platform, chat interface, FRP endpoint, nginx edge, and service ownership. |
| `docs/OPS_ENTRYPOINTS.md` | Compatibility record | Original FreeDomain-inspired ops-entrypoint plan file; points to `docs/ONLINE_DISTRIBUTIONS.md` as the expanded source of truth. |
| `docs/LIMACODE_MANAGEMENT.md` | Active | Source of truth for LiMa Code submodule governance, pinned revision updates, cross-repo verification, and admitted external workflow references. |
| `docs/ESP32S_XYZ_MANAGEMENT.md` | Active | Source of truth for esp32S_XYZ submodule governance, LiMa backend boundaries, and cross-repo product verification. |
| `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md` | Active | Optimization and refactor mandate for LiMa-led esp32S_XYZ improvement work. |
| `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md` | Active plan | Direct U8-to-LiMa Device Gateway plan; public route is deployed and now uses Redis-backed task queues plus pub/sub session-owner notification on VPS. |
| `docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md` | Active deployment record | Redis HA design and evidence for multi-process Device Gateway delivery; Postgres remains deferred for audit/history. |
| `docs/superpowers/plans/2026-05-24-xiaozhi-server-deprecation-removal.md` | Active plan | Gated deprecation, migration, quarantine, and eventual removal plan for Xiaozhi server runtime. |
| `docs/reference/HARDWARE_COMPANION_REFERENCES.md` | Active boundary | External voice/display/OCR/TTS/robotics/world-model companion hardware references admitted for later LiMa Device Gateway roadmap work. |
| `docs/reference/AI_ENGINEERING_COMPETENCY_MAP_2026.md` | Active boundary | Maps the 12 production AI engineering concepts to LiMa gates for prompts, RAG, vectors, agents/tools, reasoning, memory, streaming, inference, FinOps, fine-tuning, evals, and MLOps. |
| `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md` | Active boundary | User-provided external reference projects mapped to LiMa capabilities, target repos, license boundaries, and priorities; expanded with successive reference batches. |
| `docs/reference/MCP_CONNECTOR_CATALOG.md` | Active boundary | Candidate MCP connector catalog and least-privilege enablement policy for LiMa Server and LiMa Code; records Skills-vs-MCP separation and default-off connector rules. |
| `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md` | Active plan | Staged adoption plan for external code-intelligence, memory, agent, governance, sandbox, research, OCR/TTS, persona, and hardware-companion capabilities. |
| `docs/superpowers/plans/2026-05-25-reference-capability-implementation-roadmap.md` | Active execution roadmap | Implementation tracker that turns admitted reference ideas into LiMa-native testable slices; Device Gateway reliable-queue closure is complete and later phases remain gated. |
| `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md` | Active plan | Superpowers implementation plan for gated multi-agent autonomy, skill/gene evolution, and GitHub/VPS approval boundaries. |
| `docs/superpowers/plans/2026-05-23-techspar-mastery-loop.md` | Active record | Implemented TechSpar-inspired local mastery loop for module mastery, weak-point extraction, review scheduling, recommendations, and promotion evidence gates. |
| `docs/reference/TECHSPAR_BORROWING_NOTES.md` | Active boundary | Concept-borrowing record and license boundary for the local mastery loop. |
| `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md` | Active boundary | Concept-borrowing record for gated autonomy, role separation, and evidence-based promotion. |
| `docs/superpowers/plans/2026-05-23-lima-code-vibe-coding.md` | Active plan | LiMa Code fork integration plan for using LiMa as model router and LiMa Code as vibe coding worker/UI. |
| `docs/superpowers/plans/2026-05-22-cloudflare-workers-ai-routing.md` | Active record | Completed Cloudflare text/code routing implementation plan. |
| `docs/superpowers/plans/2026-05-22-token-safe-local-proxy-routing.md` | Active record | Completed token-safe refresh, topology-aware local proxy routing, and exact-output quality hotfix plan. |
| `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md` | Active record | Completed candidate registry, probes, stability, and quota-aware routing plan. |
| `docs/superpowers/plans/2026-05-22-complete-open-phases.md` | Active record | Completed closeout plan for IDE verification, free web AI admission, and routing optimization. |
| `docs/superpowers/plans/2026-05-22-free-model-first-tier-eval.md` | Active record | Completed SCNet/Kimi first-tier evaluation plan. |
| `docs/superpowers/plans/2026-05-22-personal-coding-assistant-eval.md` | Active record | Completed coding backend evaluation plan. |

## Historical Or Paused

These files are retained as reference, but they are not the current execution direction:

| Document | Reason |
|---|---|
| `docs/DEVELOPMENT_PLAN_v2.md` | Commercial/public-site roadmap is paused. |
| `docs/BRANDING_UNIFICATION.md` | Public brand polish is not the current priority. |
| `docs/DUAL_TRACK_ROUTING_PLAN.md` | Useful ideas remain, but current routing is evidence-backed coding-first. |
| `docs/MULTIMODAL_FEATURES_PLAN.md` | Voice/multimodal is retained but not main direction. |
| `docs/GEMINI_LIVE_PLAN.md` | Not part of the current private coding assistant loop. |
| `docs/ONEAPI_PROGRESS.md` | New API remains deployed, but commercial/open-platform rollout is paused. |
| `docs/PRODUCTION_READINESS.md` | Useful safety checklist; public commercial readiness is not the target. |

## Rules For Future Agents

1. Treat LiMa as a private personal coding assistant unless the user explicitly changes direction.
2. Do not revive payment, registration, billing, or commercial dashboard work from older docs.
3. When a runtime fact changes, update `STATUS.md` and `docs/LIMA_MEMORY.md` in the same session.
4. For free web AI expansion, use `docs/FREE_WEB_AI_EXPANSION_PLAN.md` before writing adapters.
5. Stage only relevant files. The repo contains many local reference directories and temporary experiments.
6. When reporting tests, distinguish LiMa target-suite results from unrestricted full-repo pytest collection.
7. Treat VPS public surfaces as tracked LiMa distributions; update `docs/ONLINE_DISTRIBUTIONS.md`, `infra/vps/`, `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md` when they change.
8. Treat `deepcode-cli` as the tracked LiMa Code submodule; update `docs/LIMACODE_MANAGEMENT.md`, `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md` when its pinned revision or Server/Worker contract changes.
9. Treat `esp32S_XYZ` as the tracked downstream hardware/product submodule; update `docs/ESP32S_XYZ_MANAGEMENT.md`, `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md` when its pinned revision or LiMa backend contract changes.
10. Treat MCP connectors as authority-bearing access paths, not simple prompts. Check `docs/reference/MCP_CONNECTOR_CATALOG.md` before enabling any new MCP server.
11. Treat `docs/reference/AI_ENGINEERING_COMPETENCY_MAP_2026.md` as the baseline production-AI checklist before expanding model, agent, memory, eval, cost, or deployment features.
12. Device Gateway production state is Redis HA on VPS; update `docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md` and `scripts/smoke_online_distributions.py` when changing Redis, worker count, or public port guards.
