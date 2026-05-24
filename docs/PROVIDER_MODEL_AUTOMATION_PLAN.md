# Provider Model Catalog Automation Plan

> Created: 2026-05-24
> Scope: automate discovery, verification, admission, and retirement for free
> or changing provider model lists.

## Problem

LiMa has many free or near-free model backends. Providers can add, rename,
gate, rate-limit, or remove models without warning. Static `backends.py`
entries become stale, while newly discovered free models can be unsafe for
private code if their data-retention policy allows prompt/completion logging.

Example from 2026-05-24:

- OpenRouter model page and endpoint metadata confirm
  `openrouter/elephant-alpha` exists as `Elephant Alpha`.
- Endpoint metadata says it is a 100B text model created on 2026-04-13.
- The model page warns that prompts and completions may be logged.
- Anonymous `/api/v1/models` did not list it during verification.
- `openrouter/elephant-alpha/endpoints` returned zero endpoints.
- LiMa has no local backend entry for Elephant Alpha.

Decision: Elephant Alpha is a watchlist/sandbox candidate, not a routeable
private-code backend.

## Goals

- Discover provider model-list changes automatically.
- Detect free-model additions, removals, pricing changes, endpoint loss, and
  capability changes.
- Keep routeable backend admission separate from raw provider discovery.
- Prevent private code from being sent to untrusted or logging-enabled models.
- Retire stale models without breaking known-good static configuration.
- Produce operator-readable evidence before any model enters hot routing.

## Non-Goals

- Do not let provider catalogs directly mutate production routing.
- Do not add new provider dependencies beyond existing HTTP clients.
- Do not send private code, repository context, credentials, or user data during
  discovery or admission.
- Do not treat provider marketing pages as proof of routeability.
- Do not auto-promote free models into IDE/coding first tier.

## Data Files

Recommended new files:

- `data/provider_model_catalog.json`
  - Raw provider catalog snapshots after normalization.
- `data/provider_model_catalog_previous.json`
  - Last accepted snapshot for diffing.
- `data/provider_model_deltas.json`
  - Added, removed, changed, and suspicious models.
- `data/backend_admission.json`
  - LiMa-owned admission state for candidate and routeable backends.
- `docs/PROVIDER_MODEL_CATALOG_REPORT.md`
  - Human-readable report generated from the latest run.

`backends.py` remains the conservative static baseline. Dynamic discovery writes
candidate overlays only.

## Model State Machine

| State | Meaning | Can Route? |
|---|---|---|
| `discovered` | Seen in provider catalog or watchlist metadata. | No |
| `watchlist` | Known by URL/id but missing from public model list or endpoint list. | No |
| `sandbox_candidate` | Has at least one endpoint and safe synthetic smoke can run. | No |
| `admitted_late_fallback` | Passed harmless smoke and minimal fixtures. | Only non-private, late fallback |
| `admitted_code_floor` | Passed coding floor eval and policy gates. | Limited coding route |
| `admitted_primary` | Passed stronger eval, stability, and human approval. | Yes |
| `draining` | Previously routeable but provider list/smoke is failing. | No new traffic |
| `retired` | Removed or repeatedly failing beyond grace period. | No |

## Provider Discovery

Initial providers:

- OpenRouter
  - Catalog: `https://openrouter.ai/api/v1/models`
  - Endpoint metadata:
    `https://openrouter.ai/api/v1/models/{model_id}/endpoints`
  - Watchlist direct checks for models like `openrouter/elephant-alpha`.

Future providers can be added through a provider adapter interface:

```python
class ProviderCatalogAdapter:
    provider: str
    def fetch_catalog(self) -> list[ProviderModel]: ...
    def fetch_endpoint_metadata(self, model_id: str) -> ProviderEndpointStatus: ...
```

## Normalized Model Record

Each model should normalize to:

```json
{
  "provider": "openrouter",
  "model_id": "openrouter/elephant-alpha",
  "name": "Elephant Alpha",
  "created_at": "2026-04-13T03:56:38Z",
  "context_length": 262144,
  "max_output_tokens": 32768,
  "modalities": ["text"],
  "pricing": {"prompt": null, "completion": null},
  "free": null,
  "endpoint_count": 0,
  "data_policy": {
    "prompts_logged": true,
    "completions_logged": true,
    "private_code_allowed": false
  },
  "source_urls": [
    "https://openrouter.ai/openrouter/elephant-alpha",
    "https://openrouter.ai/api/v1/models/openrouter/elephant-alpha/endpoints"
  ],
  "last_seen_at": "2026-05-24T00:00:00Z",
  "routeable": false,
  "reason": "endpoint_count_zero"
}
```

## Discovery Pipeline

1. Fetch provider catalogs and watchlist endpoint metadata.
2. Normalize each provider response into `ProviderModel`.
3. Compare with previous snapshot.
4. Classify deltas:
   - `added`
   - `removed`
   - `endpoint_count_changed`
   - `pricing_changed`
   - `context_changed`
   - `data_policy_changed`
   - `capability_changed`
5. Write JSON evidence and Markdown report.
6. Queue only safe candidates for smoke/admission.

## Admission Pipeline

Admission must be separate from discovery.

1. Eligibility gate:
   - provider API key exists if required;
   - endpoint count is greater than zero;
   - model appears in catalog or watchlist endpoint metadata;
   - data policy allows the target traffic class.
2. Harmless smoke:
   - use public, synthetic prompts only;
   - verify non-streaming 200;
   - optionally verify streaming;
   - record latency and exact backend id.
3. Fixture eval:
   - route through `scripts/eval_coding_backends.py` only after smoke;
   - use synthetic coding fixtures, not private repositories;
   - require exact-output and JSON/tool-shape checks for IDE/code routing.
4. Human promotion:
   - required for `admitted_code_floor` or above;
   - required if prompts/completions may be logged;
   - required if provider price/free status changed.

## Routing Policy

Router selection should require all of:

- backend exists in static `BACKENDS` or approved runtime overlay;
- `enabled=true`;
- admission state is routeable for the request type;
- `private_code_allowed=true` for IDE/code/private repository traffic;
- provider/model is not cooled down, draining, or retired;
- key/budget state is available.

Recommended policy by traffic class:

| Traffic | Allowed States |
|---|---|
| harmless probe | `sandbox_candidate+` |
| public/simple chat | `admitted_late_fallback+` |
| private chat | `admitted_code_floor+` and `private_code_allowed=true` |
| IDE/coding | `admitted_code_floor+` and coding eval pass |
| primary coding | `admitted_primary` only |

## Retirement Pipeline

A model enters `draining` when any of these persist for N runs:

- removed from provider catalog;
- endpoint count becomes zero;
- repeated 404/model-not-found;
- repeated auth/quota/rate-limit state not tied to local key exhaustion;
- provider changes data policy to logging-enabled for private traffic;
- pricing changes from free to paid without approval.

After a grace period, move to `retired`. Keep historical evidence and do not
delete static config automatically.

## Commands

Proposed commands:

```powershell
python scripts/provider_model_catalog.py discover --provider openrouter
python scripts/provider_model_catalog.py diff
python scripts/provider_model_catalog.py report
python scripts/provider_model_admission.py smoke --provider openrouter --safe-only
python scripts/provider_model_admission.py eval --candidate or_elephant_alpha
```

## Tests

Minimum unit tests:

- OpenRouter catalog normalization handles normal `/api/v1/models` entries.
- Watchlist endpoint metadata handles models missing from `/api/v1/models`.
- Endpoint count zero marks model non-routeable.
- Logging-enabled data policy sets `private_code_allowed=false`.
- Deltas detect added, removed, pricing, endpoint, and data-policy changes.
- Admission refuses private-code routing without explicit approval.
- Draining/retired backends are excluded from router selection.
- Report redacts API keys and never includes prompt contents.

## Automation Schedule

Suggested cadence:

- Catalog discovery: every 6 hours.
- Endpoint metadata for current backends: hourly.
- Watchlist candidates: every 12 hours.
- Harmless smoke for admitted free models: every 2-4 hours with quota cap.
- Coding eval: manual or daily for changed candidates only.

## Rollback

Dynamic overlay updates must be reversible:

- keep timestamped snapshots;
- never delete static `backends.py` entries automatically;
- support `--restore data/provider_model_catalog_previous.json`;
- if catalog automation fails, router continues using the last admitted static
  configuration.

## First Implementation Slice

Recommended first slice:

1. Add provider catalog data classes and OpenRouter adapter.
2. Add snapshot/diff writer.
3. Add Elephant Alpha watchlist test fixture:
   - model metadata exists;
   - endpoint count zero;
   - prompts/completions logging detected;
   - final state is `watchlist`, not routeable.
4. Generate `docs/PROVIDER_MODEL_CATALOG_REPORT.md`.
5. Do not change routing yet.
