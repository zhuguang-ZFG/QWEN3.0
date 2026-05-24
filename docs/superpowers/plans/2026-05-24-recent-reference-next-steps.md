# Recent Reference Next-Step Execution Plan

**Date:** 2026-05-24
**Status:** planned
**Scope:** organize the newest reference inputs into executable LiMa follow-up
lanes after the current M11 implementation.

## Purpose

This document turns the recent reference batch into a practical backlog. It
does not redirect the active M11 implementation. M11 should continue as the
current DevOps, deployment, and terminal UX milestone. The references below are
queued as follow-up lanes with explicit gates, tests, and adoption boundaries.

The goal is to avoid two failure modes:

- treating every interesting reference as a dependency to import;
- letting useful ideas vanish into chat history without a concrete execution
  path.

## Current Decision

Keep the active path unchanged:

1. Finish the current M11 code batch.
2. Codex reviews, fixes closure gaps, runs focused and full verification,
   updates docs, commits, and pushes.
3. Only then pull from this reference plan for the next batch.

Use the lane labels `N1`, `N2`, etc. for now. They can later become official
milestones or sub-milestones without renumbering the existing plan.

## Recent Reference Inventory

| Reference | Current Status | Primary Lane | Runtime Adoption |
|---|---|---|---|
| `affaan-m/ECC` | Cloned to `D:/GIT/ecc-ref` and skimmed | N3 Operator Shell | Pattern only; no dependency |
| `mvanhorn/last30days-skill` | User-provided repo reference | N2 Research Radar | Future opt-in adapter |
| `jingyaogong/minimind` | User-provided repo reference | N4 Local Model Lab | Future isolated experiment |
| `lzjun567/zhihu-api` | Local reference exists at `D:/GIT/zhihu-api-ref` | N2 Research Radar | Default-off connector |
| Juejin article | User-provided URL | N2/N6 methodology | Extract later with source record |
| WeChat article | User-provided URL | N2/N6 methodology | Extract later with source record |
| Multi-agent coding papers: AgentConductor, Solvita, RecursiveMAS, Qoder | User-provided summary recorded in progress | N6 Multi-Agent Coding Modes | Concept only until benchmarked |
| OpenRouter Elephant Alpha and volatile free-model lists | Prior verification summarized in `findings.md` as CQ-028 | N1 Provider Model Automation | Watchlist until probe passes |
| IDrive e2 S3-compatible 10GB free storage | User-provided service note | N5 Artifact Backup | Optional private archive only |

## Cross-Cutting Adoption Rules

1. No new runtime dependency from a reference repo without license, security,
   data-flow, and rollback review.
2. Every connector starts `default_off`.
3. Any provider, web, social, browser, cloud, storage, local training, or
   messaging lane must define credential custody before code execution.
4. Any data-ingestion lane must use M10-style manifests, retention, redaction,
   and artifact root constraints.
5. Any agent/team/autonomy lane must use M7 tool authority classes and approval
   gates.
6. Any model/provider automation lane must never hot-route a model just because
   it appears in a remote catalog.
7. Any external article or web post must be stored as a source artifact with
   retrieval date before it becomes evidence in docs or code comments.

## Recommended Execution Order

| Order | Lane | Why First/Next | Expected Size |
|---:|---|---|---|
| 0 | Finish current M11 | Already in progress | Current batch |
| 1 | N1 Provider Model Automation | Directly solves free-model churn and Elephant Alpha uncertainty | Medium |
| 2 | N2 Research Radar | Builds on M10 manifests and captures last30days/Zhihu/article references | Medium |
| 3 | N3 Operator Shell | ECC-inspired UX after M11 CLI/deployment baseline exists | Medium-large |
| 4 | N5 Artifact Backup | Useful once research/model snapshots produce artifacts | Small-medium |
| 5 | N4 Local Model Lab | MiniMind needs stronger data/eval isolation before code | Medium-large |
| 6 | N6 Multi-Agent Coding Modes | Needs eval, worker governance, and operator shell signals first | Large |

## N1 - Provider Model Automation

### Goal

Automatically detect provider free-model changes, probe them safely, and update
LiMa routing candidates without manual guesswork. This lane handles volatile
free models and watchlist claims such as Elephant Alpha.

### Key References

- OpenRouter Elephant Alpha investigation and CQ-028.
- Existing LiMa backend registry, key pool, health tracker, reputation, budget,
  and observability modules.
- Existing free-model and web-reverse evaluation artifacts.

### Slice N1-S1: Provider Catalog Snapshot Schema

Implement a local schema for provider catalog snapshots.

Likely files:

- `provider_automation/__init__.py`
- `provider_automation/catalog.py`
- `tests/test_provider_automation.py`
- `docs/PROVIDER_MODEL_AUTOMATION_PLAN.md`

Data structures:

- `ProviderModelSnapshot`
  - provider
  - model_id
  - display_name
  - source
  - fetched_at
  - pricing_class
  - context_window
  - supports_streaming
  - supports_tools
  - supports_json
  - privacy_note
  - raw_endpoint_count
  - admission_status
  - evidence_refs
- `ProviderCatalogDelta`
  - added
  - removed
  - changed
  - unchanged
  - generated_at

Tests:

- snapshot JSON round-trip;
- unknown fields ignored or preserved safely;
- secret-like metadata redacted;
- delta detects added, removed, and changed model rows.

Exit criteria:

- Catalog changes can be represented without touching `backends.py`.
- No model is routeable from catalog presence alone.

### Slice N1-S2: Source Fetcher Boundary

Add source-specific fetcher interfaces and one OpenRouter fetcher behind a
network gate.

Likely files:

- `provider_automation/sources.py`
- `provider_automation/openrouter.py`
- `tests/test_provider_sources.py`

Rules:

- Default tests use fixtures, not live network.
- Live fetch requires explicit CLI flag or env gate.
- Fetch failures produce `network_error`, `auth_error`, or `malformed_response`
  classes compatible with M1/M6 telemetry.

Tests:

- fixture OpenRouter model list parses;
- endpoint-less model is marked watchlist, not admitted;
- privacy notes survive as redacted metadata;
- malformed JSON is classified.

Exit criteria:

- Elephant-like models can be recorded as `watchlist` with evidence and reason.

### Slice N1-S3: Safe Probe Harness

Probe candidate models with harmless prompts before admission.

Likely files:

- `provider_automation/probe.py`
- `tests/test_provider_probe.py`
- Extend or reuse `coding_eval.py` fixtures.

Probe levels:

- `metadata_only`: model exists in catalog.
- `completion_smoke`: harmless exact-output prompt.
- `stream_smoke`: optional streaming chunk check.
- `coding_fixture`: tiny deterministic coding prompt.
- `quality_gate`: M5 result check.

Admission outcomes:

- `rejected`
- `watchlist`
- `sandbox_only`
- `candidate`
- `routing_enabled`

Tests:

- catalog-only model never becomes `routing_enabled`;
- anonymous/quota failures become `watchlist` or `sandbox_only`;
- privacy-risk note prevents automatic routing unless manually allowed;
- successful exact-output and quality gate can promote to `candidate`.

Exit criteria:

- Provider updates create evidence, not silent route changes.

### Slice N1-S4: Registry Diff Report

Generate a human-readable and JSON report for changed provider catalogs.

Likely files:

- `provider_automation/report.py`
- `scripts/provider_refresh.py` or future `lima provider-refresh`
- `tests/test_provider_report.py`

Report fields:

- added free models;
- removed free models;
- models with changed pricing/privacy/endpoint status;
- currently routed models that disappeared upstream;
- candidate models requiring probe;
- recommended manual actions.

Exit criteria:

- The user can see what changed before accepting any route update.

### Slice N1-S5: Route Admission Patch Plan

Produce a proposed patch plan, not an automatic edit to `backends.py`.

Likely files:

- `provider_automation/admission.py`
- `tests/test_provider_admission.py`

Rules:

- New route entries require passing probe evidence.
- Removed upstream models are cooled or disabled, not deleted blindly.
- Free models with logging/training warnings require explicit privacy label.
- All route changes include rollback instructions.

Exit criteria:

- LiMa can automate 80% of provider refresh work while preserving human review.

## N2 - Research Radar

### Goal

Create a local-first research and trend radar for coding, provider, model, and
product references. It should use M10 manifests and avoid account/cookie risk.

### Key References

- `last30days-skill`
- `zhihu-api`
- Juejin article
- WeChat article
- Existing `data_workbench` manifest/policy
- Existing research notes in `progress.md`

### Slice N2-S1: Source Registry

Create a source registry for research inputs.

Likely files:

- `research_radar/__init__.py`
- `research_radar/sources.py`
- `tests/test_research_radar.py`
- `docs/RESEARCH_RADAR_PLAN.md`

Source fields:

- source_id
- source_type: `repo`, `article`, `social`, `forum`, `paper`, `provider_page`
- url
- auth_mode: `none`, `api_key`, `cookie`, `manual_export`
- default_status: `enabled`, `disabled`, `watchlist`
- terms_risk
- rate_limit
- retention_days
- evidence_policy

Rules:

- Cookie/session sources default disabled.
- Social/community scraping requires platform policy review.
- Manual pasted summaries are marked as `user_provided`, not independently
  verified.

Exit criteria:

- The recent sources can be listed without activating network behavior.

### Slice N2-S2: Artifact-Backed Research Runs

Represent each research run as manifests plus structured findings.

Likely files:

- `research_radar/run.py`
- `research_radar/findings.py`
- `tests/test_research_radar_runs.py`

Run fields:

- query
- time_window
- sources
- fetched_at
- artifacts
- summary
- confidence
- follow_up_tasks

Use M10:

- every fetched article/list becomes an `ArtifactManifest`;
- summaries are redacted;
- file paths stay under `LIMA_ARTIFACT_ROOT`;
- retention defaults to 30 days unless overridden.

Exit criteria:

- Research output is traceable to source artifacts and dates.

### Slice N2-S3: last30days-Style Time-Windowed Radar

Implement the LiMa-native version of the last30days pattern.

Initial scope:

- GitHub repo activity;
- public article links manually provided by user;
- optional provider release pages.

Out of scope:

- Reddit/social login;
- cookie-based scraping;
- posting or commenting;
- personal account automation.

Exit criteria:

- A weekly radar can say what changed recently and why it matters.

### Slice N2-S4: Zhihu/Juejin/WeChat Handling Policy

Define how Chinese web/community references enter LiMa.

Rules:

- Prefer manual source export or public URL metadata first.
- Do not store cookies in LiMa.
- Do not bypass platform access controls.
- Treat unstable pages as source artifacts with retrieval date.
- Keep connector code default-off until terms/rate/privacy review exists.

Exit criteria:

- These sources can inform planning without turning into hidden scraping.

### Slice N2-S5: Research-to-Backlog Converter

Convert findings into backlog proposals.

Proposal fields:

- title
- reference
- capability
- target module
- adoption type: `concept`, `adapter`, `test_fixture`, `doc_only`
- risk class
- suggested slice
- verification command

Exit criteria:

- New references become reviewable work items, not loose notes.

## N3 - Operator Shell Inspired By ECC

### Goal

Build a LiMa operator shell that can diagnose, summarize, and repair local
configuration drift. ECC is the main reference, but LiMa should stay Python
native and focused on its router/worker/service surface.

### Key References

- `D:/GIT/ecc-ref/scripts/ecc.js`
- `D:/GIT/ecc-ref/scripts/doctor.js`
- `D:/GIT/ecc-ref/scripts/platform-audit.js`
- `D:/GIT/ecc-ref/scripts/observability-readiness.js`
- `D:/GIT/ecc-ref/scripts/operator-readiness-dashboard.js`

### Slice N3-S1: LiMa Status Contract

Define a versioned status payload.

Likely files:

- `operator_shell/__init__.py`
- `operator_shell/status.py`
- `tests/test_operator_shell.py`
- `docs/OPERATOR_SHELL_PLAN.md`

Status sections:

- service
- backend_registry
- key_pool
- free_models
- routing
- observability
- memory
- data_workbench
- sandbox
- tool_gateway
- deployment

Exit criteria:

- Status JSON can be generated without network or secrets.

### Slice N3-S2: `lima doctor`

Diagnose local readiness.

Checks:

- Python version;
- required modules;
- env vars present or intentionally absent;
- data directories writable;
- manifest path safe;
- SQLite paths isolated;
- provider registry valid;
- test fixtures present;
- port availability if service config is known.

Exit criteria:

- A developer can run one command and see blockers plus fixes.

### Slice N3-S3: `lima status`

Print human table plus JSON.

Outputs:

- total backends;
- routeable coding backends;
- free/limited model counts;
- key-pool exhausted providers;
- recent failure classes;
- top failing backends;
- token usage snapshot;
- quality score summary.

Exit criteria:

- Status is useful during a deployment incident.

### Slice N3-S4: `lima smoke`

Run deterministic no-secret smoke checks.

Checks:

- import key modules;
- load backend registry;
- run quality gate fixture;
- run fake sandbox fixture;
- write/read temp artifact manifest;
- record one observability event;
- classify one representative failure.

Exit criteria:

- New machine baseline can pass without real provider keys.

### Slice N3-S5: `lima repair --dry-run`

Generate fix suggestions without mutating by default.

Examples:

- missing `.env` key names;
- unwritable data directory;
- stale manifest path;
- missing optional directories;
- registry model missing capability metadata.

Rules:

- Dry-run first.
- Mutating repair requires explicit flag.
- Never creates or edits secrets.

Exit criteria:

- Operator shell can guide fixes without becoming risky automation.

### Slice N3-S6: Operator Readiness Dashboard

Generate a markdown/JSON readiness snapshot.

Readiness gates:

- no blocking tracked diffs for release claims;
- full suite command recorded;
- M11 deployment docs present;
- smoke passes;
- provider watchlist reviewed;
- no raw secrets in diagnostics;
- optional VPS deployment smoke evidence attached.

Exit criteria:

- Release/deploy readiness becomes an artifact, not a vibe.

## N4 - Local Model Lab With MiniMind

### Goal

Create a local model experiment lane for small training/eval experiments,
without mixing it into production routing or private user data.

### Key References

- `jingyaogong/minimind`
- Existing `coding_eval.py`
- Existing M10 data workbench
- Existing M8 sandbox provider

### Slice N4-S1: Source And License Review

Before code:

- clone/read MiniMind;
- record license;
- identify training scripts, data assumptions, model sizes, export formats;
- record hardware requirements and Windows compatibility;
- decide whether it is concept-only or experiment-ready.

Exit criteria:

- A source review doc exists before any runtime integration.

### Slice N4-S2: Training Data Policy

Define what data can enter local training.

Allowed first:

- public toy datasets;
- synthetic fixtures;
- small coding eval examples explicitly marked for training.

Blocked:

- private chat transcripts;
- provider prompts/responses;
- user files;
- secrets;
- production logs;
- hardware telemetry.

Exit criteria:

- Tests prove training manifests reject restricted data classes.

### Slice N4-S3: Eval-First Local Model Harness

Evaluate before training.

Likely files:

- `local_model_lab/__init__.py`
- `local_model_lab/eval.py`
- `tests/test_local_model_lab.py`

Metrics:

- exact-output;
- code fixture pass/fail;
- refusal correctness for unsafe prompts;
- latency;
- memory footprint.

Exit criteria:

- A tiny local model can be evaluated without becoming a LiMa backend.

### Slice N4-S4: Isolated Training Smoke

Run one tiny training or fine-tuning smoke only if source review passes.

Rules:

- local only;
- no private data;
- output under artifact root;
- manifest records model artifact;
- no automatic route admission.

Exit criteria:

- Training can produce an artifact and eval report, but routing remains manual.

### Slice N4-S5: Optional Backend Candidate Adapter

Only after eval:

- add candidate backend metadata;
- mark `default_off`;
- require manual enable;
- run coding fixtures before route admission.

Exit criteria:

- Local model experiments cannot degrade production routing accidentally.

## N5 - Artifact Backup And IDrive e2

### Goal

Evaluate cheap private object storage for non-public artifacts, snapshots, and
reports. IDrive e2 is useful only as private S3-compatible storage unless paid
public buckets are later justified.

### Key Reference

- User note: IDrive e2 free 10GB object storage, S3-compatible, public buckets
  require paid plan, downloads not rate-limited.

### Slice N5-S1: Storage Role Decision

Accepted use cases:

- encrypted/private artifact backup;
- provider catalog snapshots;
- research radar artifacts;
- eval reports;
- operator dashboard snapshots.

Rejected first:

- public static hosting;
- public model/file CDN;
- secrets backup;
- unencrypted private datasets;
- production dependency for local development.

Exit criteria:

- Storage role is documented before any S3 client code.

### Slice N5-S2: Storage Provider Interface

Likely files:

- `artifact_storage/__init__.py`
- `artifact_storage/provider.py`
- `tests/test_artifact_storage.py`

Interface:

- `put_artifact(manifest, local_path)`
- `get_artifact(artifact_id, destination)`
- `list_artifacts(prefix)`
- `delete_artifact(artifact_id)`
- `verify_roundtrip()`

Default provider:

- local filesystem fake provider.

Exit criteria:

- Tests pass without cloud credentials.

### Slice N5-S3: Optional S3-Compatible Adapter

Rules:

- env-gated;
- no default dependency if avoidable;
- credentials never logged;
- bucket must be private;
- object key path normalized;
- retention follows manifest.

Exit criteria:

- IDrive e2 can be tested manually without becoming required infrastructure.

## N6 - Multi-Agent Coding Modes

### Goal

Use multi-agent research as design pressure for safer and more efficient coding
workflows, not as immediate role sprawl.

### Key References

- AgentConductor
- Solvita
- RecursiveMAS
- Qoder
- Existing M7 worker governance
- Existing M5 evals and M6 observability

### Slice N6-S1: Task Difficulty Classifier

Inspired by AgentConductor.

Inputs:

- task size;
- files touched;
- risk class;
- required tools;
- test scope;
- ambiguity;
- user deadline.

Outputs:

- `single_owner`
- `owner_plus_reviewer`
- `owner_plus_researcher`
- `planner_solver_reviewer`
- `full_team_required`

Rules:

- Start with conservative heuristics.
- More agents require evidence and an audit reason.

Exit criteria:

- Simple tasks stay simple.

### Slice N6-S2: Opt-In Solvita Role Loop

Roles:

- planner;
- solver;
- oracle/reviewer;
- hacker/adversarial tester.

Rules:

- Only for coding/eval tasks.
- Every role output is an artifact or structured note.
- No role can execute tools outside task authority.

Exit criteria:

- Role loops are testable and auditable.

### Slice N6-S3: Compact Agent Communication Envelope

Inspired by RecursiveMAS.

Replace verbose agent chatter with:

- artifact refs;
- file refs;
- claim;
- evidence;
- risk;
- requested action;
- confidence;
- token budget.

Exit criteria:

- Multi-agent communication becomes cheaper and easier to review.

### Slice N6-S4: Qoder-Style Software Engineering Workflow

Use Qoder as product/workflow reference.

Workflow stages:

- repo understanding;
- task decomposition;
- implementation;
- test repair;
- code review;
- deployment/readiness;
- memory update.

Exit criteria:

- Long coding work has durable checkpoints and does not depend on one huge
  context window.

### Slice N6-S5: Evaluation Gate

Compare modes:

- single owner;
- owner + reviewer;
- planner/solver/reviewer;
- full role loop.

Metrics:

- pass rate;
- latency;
- token estimate;
- number of files touched;
- review defects;
- rollback difficulty.

Exit criteria:

- Multi-agent mode expands only when evidence beats simpler execution.

## Source Extraction Backlog

These sources should be converted into small source records before they drive
implementation details:

1. Juejin article:
   - fetch or manually archive;
   - record title, author if visible, retrieval date, main claims;
   - map claims to N2/N6 only.
2. WeChat article:
   - fetch or manually archive;
   - preserve only summary, not full copyrighted content;
   - map methodology claims to N2/N6.
3. Zhihu API reference:
   - inspect license and auth/session requirements;
   - record whether anonymous read is possible;
   - keep connector default-off.
4. last30days:
   - inspect license, source list, credential needs, rate limits;
   - convert only the time-windowed research pattern first.
5. MiniMind:
   - inspect license, training data assumptions, hardware needs;
   - keep isolated from production routing.
6. ECC:
   - extract operator-shell patterns only;
   - do not copy installer/plugin machinery into LiMa.

## Definition Of Ready For Any Lane

A lane can start when it has:

- source records and license notes;
- target LiMa module list;
- data-flow diagram or short prose equivalent;
- credential and authority boundary;
- tests planned;
- rollback note;
- no conflict with current milestone work.

## Definition Of Done For Any Slice

A slice is done only when:

- focused tests pass;
- full suite passes if production code changed;
- `git diff --check` passes;
- docs/progress are updated;
- no unrelated untracked files are staged;
- new network/cloud/provider behavior is default-off unless explicitly approved;
- Codex review has checked security, redaction, path handling, and import-time
  env capture risks.

## Suggested First Follow-Up After M11

Start with **N1 Provider Model Automation**.

Reason:

- It directly addresses real operational pain: free models disappear and new
  free models appear without warning.
- It keeps risky models such as Elephant Alpha on a watchlist until live probe
  evidence exists.
- It reuses existing LiMa modules: backend registry, key pool, budget,
  reputation, quality gate, observability, and eval fixtures.
- It can land in small, testable slices without changing production routing.

Recommended first commit:

1. Add provider catalog snapshot dataclasses.
2. Add fixture-based OpenRouter catalog parser.
3. Add delta report tests.
4. Add docs explaining that catalog presence is not route admission.

Recommended second commit:

1. Add harmless probe harness.
2. Add admission statuses.
3. Add watchlist/sandbox/candidate/routing-enabled tests.
4. Add a report command or function.

Only after those two commits should LiMa propose changes to `backends.py`.
