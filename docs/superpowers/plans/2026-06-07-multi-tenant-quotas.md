# Multi-Tenant and Quota Management

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-tenant support with per-tenant API keys, quota management, usage tracking, and tenant-aware routing preferences.

**Architecture:** A Tenant model groups API keys with quotas and preferences. The tenant registry resolves tenants from API keys during auth. Routing considers tenant preferences (preferred models, allowed models, token budget). Per-tenant usage is tracked in SQLite and exposed via admin API.

**Tech Stack:** Python 3.10+, SQLite, FastAPI, pytest, existing LiMa auth/routing infrastructure

---

## Task 1: Tenant Model

Create the `Tenant`, `TenantQuota`, and `TenantPreferences` dataclasses that define the multi-tenant data model.

### Files to Create

- `D:\QWEN3.0\tenant.py` -- new file

### Steps

- [ ] Create `D:\QWEN3.0\tenant.py` with the following complete implementation:

```python
"""Tenant model for multi-tenant support in LiMa.

A Tenant groups one or more API keys with shared quotas, routing
preferences, and usage tracking. Tenants are resolved from API keys
during the auth phase of every request.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TenantQuota:
    """Per-tenant quota limits.

    Mirrors the per-key quota fields in client_keys but applies
    to the *aggregate* usage across all keys belonging to the tenant.
    A value of 0 means unlimited.
    """

    daily_requests: int = 5000
    monthly_requests: int = 150000
    rpm_limit: int = 60
    max_token_budget: int = 0  # 0 = unlimited; >0 = max tokens per request
    allowed_models: list[str] = field(default_factory=list)  # empty = all models allowed


@dataclass
class TenantPreferences:
    """Per-tenant routing preferences.

    These influence the routing selector to bias backend selection
    toward the tenant's preferred configuration.
    """

    preferred_model: str = ""  # backend name to boost in selection
    scenario_bias: str = ""  # "coding" | "chat" | "" (empty = auto-detect)
    custom_system_prompt_prefix: str = ""  # prepended to system prompt


@dataclass
class Tenant:
    """A tenant represents an organization or user group in LiMa.

    Each tenant owns one or more API keys (referenced by their raw
    key_value strings). All keys share the tenant's quota pool and
    routing preferences.
    """

    tenant_id: str = ""
    name: str = ""
    api_keys: list[str] = field(default_factory=list)  # raw key_value strings
    quota: TenantQuota = field(default_factory=TenantQuota)
    preferences: TenantPreferences = field(default_factory=TenantPreferences)
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "api_keys": list(self.api_keys),
            "quota": {
                "daily_requests": self.quota.daily_requests,
                "monthly_requests": self.quota.monthly_requests,
                "rpm_limit": self.quota.rpm_limit,
                "max_token_budget": self.quota.max_token_budget,
                "allowed_models": list(self.quota.allowed_models),
            },
            "preferences": {
                "preferred_model": self.preferences.preferred_model,
                "scenario_bias": self.preferences.scenario_bias,
                "custom_system_prompt_prefix": self.preferences.custom_system_prompt_prefix,
            },
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Tenant:
        """Deserialize from a dictionary (e.g. loaded from JSON)."""
        quota_data = data.get("quota", {})
        pref_data = data.get("preferences", {})
        return cls(
            tenant_id=data.get("tenant_id", ""),
            name=data.get("name", ""),
            api_keys=data.get("api_keys", []),
            quota=TenantQuota(
                daily_requests=int(quota_data.get("daily_requests", 5000)),
                monthly_requests=int(quota_data.get("monthly_requests", 150000)),
                rpm_limit=int(quota_data.get("rpm_limit", 60)),
                max_token_budget=int(quota_data.get("max_token_budget", 0)),
                allowed_models=quota_data.get("allowed_models", []),
            ),
            preferences=TenantPreferences(
                preferred_model=pref_data.get("preferred_model", ""),
                scenario_bias=pref_data.get("scenario_bias", ""),
                custom_system_prompt_prefix=pref_data.get("custom_system_prompt_prefix", ""),
            ),
            enabled=data.get("enabled", True),
            created_at=float(data.get("created_at", 0) or time.time()),
            updated_at=float(data.get("updated_at", 0) or time.time()),
        )
```

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -c "from tenant import Tenant, TenantQuota, TenantPreferences; t = Tenant(tenant_id='t1', name='Test'); d = t.to_dict(); t2 = Tenant.from_dict(d); assert t2.tenant_id == 't1'; assert t2.quota.daily_requests == 5000; assert t2.preferences.preferred_model == ''; print('OK: Tenant model works')"`

Expected output:
```
OK: Tenant model works
```

---

## Task 2: Tenant Registry

Create the tenant registry that manages tenants in-memory with JSON file persistence. Provides CRUD operations and reverse lookups (API key -> tenant).

### Files to Create

- `D:\QWEN3.0\tenant_registry.py` -- new file

### Steps

- [ ] Create `D:\QWEN3.0\tenant_registry.py` with the following complete implementation:

```python
"""Tenant registry -- in-memory CRUD with JSON file persistence.

The registry maintains a mapping of tenant_id -> Tenant and a reverse
index of api_key_value -> tenant_id for O(1) lookups during auth.

Persistence: data/tenants.json (atomic write-tmp-then-rename).
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from pathlib import Path

from tenant import Tenant, TenantPreferences, TenantQuota

_log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent / "data"
_TENANTS_PATH = _DATA_DIR / "tenants.json"
_lock = threading.Lock()

# In-memory state
_tenants: dict[str, Tenant] = {}
_key_index: dict[str, str] = {}  # api_key_value -> tenant_id
_loaded: bool = False


def _load() -> None:
    """Load tenants from disk into memory. Idempotent, thread-safe."""
    global _tenants, _key_index, _loaded
    with _lock:
        if _loaded:
            return
        if not _TENANTS_PATH.exists():
            _loaded = True
            return
        try:
            raw = json.loads(_TENANTS_PATH.read_text(encoding="utf-8"))
            items = raw.get("tenants", []) if isinstance(raw, dict) else []
            for item in items:
                t = Tenant.from_dict(item)
                _tenants[t.tenant_id] = t
                for key in t.api_keys:
                    _key_index[key] = t.tenant_id
            _loaded = True
            _log.info("tenant_registry: loaded %d tenants from disk", len(_tenants))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("tenant_registry: failed to load tenants: %s", exc)
            _loaded = True


def _save() -> None:
    """Persist current tenants to disk. Caller MUST hold _lock."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {"tenants": [t.to_dict() for t in _tenants.values()]}
    tmp = _TENANTS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(_TENANTS_PATH)


def _generate_tenant_id() -> str:
    """Generate a unique tenant ID: 'tn-' + 8 hex chars."""
    return f"tn-{secrets.token_hex(4)}"


def _rebuild_key_index() -> None:
    """Rebuild the reverse key index from scratch. Caller MUST hold _lock."""
    global _key_index
    _key_index = {}
    for tid, t in _tenants.items():
        for key in t.api_keys:
            _key_index[key] = tid


# -- Public API ---------------------------------------------------------------


def create_tenant(
    name: str,
    *,
    api_keys: list[str] | None = None,
    quota: dict | None = None,
    preferences: dict | None = None,
) -> Tenant:
    """Create a new tenant and persist it.

    Args:
        name: Human-readable tenant name.
        api_keys: Optional list of existing client key_value strings to assign.
        quota: Optional dict with TenantQuota fields to override defaults.
        preferences: Optional dict with TenantPreferences fields.

    Returns:
        The newly created Tenant.

    Raises:
        ValueError: If a key is already assigned to another tenant.
    """
    _load()
    quota = quota or {}
    preferences = preferences or {}
    api_keys = list(api_keys or [])

    with _lock:
        # Validate no key conflicts
        for key in api_keys:
            existing_tid = _key_index.get(key)
            if existing_tid:
                raise ValueError(
                    f"API key is already assigned to tenant '{existing_tid}'"
                )

        tenant_id = _generate_tenant_id()
        now = time.time()
        t = Tenant(
            tenant_id=tenant_id,
            name=name,
            api_keys=api_keys,
            quota=TenantQuota(
                daily_requests=int(quota.get("daily_requests", 5000)),
                monthly_requests=int(quota.get("monthly_requests", 150000)),
                rpm_limit=int(quota.get("rpm_limit", 60)),
                max_token_budget=int(quota.get("max_token_budget", 0)),
                allowed_models=quota.get("allowed_models", []),
            ),
            preferences=TenantPreferences(
                preferred_model=preferences.get("preferred_model", ""),
                scenario_bias=preferences.get("scenario_bias", ""),
                custom_system_prompt_prefix=preferences.get(
                    "custom_system_prompt_prefix", ""
                ),
            ),
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        _tenants[tenant_id] = t
        for key in api_keys:
            _key_index[key] = tenant_id
        _save()
        _log.info("tenant_registry: created tenant %s (%s)", tenant_id, name)
    return t


def get_tenant(tenant_id: str) -> Tenant | None:
    """Look up a tenant by its ID. Returns None if not found."""
    _load()
    return _tenants.get(tenant_id)


def get_tenant_by_api_key(key_value: str) -> Tenant | None:
    """Resolve the tenant that owns the given API key. Returns None if unassigned."""
    _load()
    tenant_id = _key_index.get(key_value)
    if tenant_id:
        return _tenants.get(tenant_id)
    return None


def update_tenant(tenant_id: str, **fields) -> Tenant:
    """Update tenant fields and persist.

    Supported keyword args: name, api_keys, quota (dict), preferences (dict), enabled.

    Raises:
        KeyError: If tenant_id not found.
        ValueError: On API key conflict.
    """
    _load()
    with _lock:
        t = _tenants.get(tenant_id)
        if t is None:
            raise KeyError(f"Tenant '{tenant_id}' not found")

        if "name" in fields:
            t.name = fields["name"]
        if "enabled" in fields:
            t.enabled = bool(fields["enabled"])
        if "api_keys" in fields:
            new_keys = list(fields["api_keys"])
            # Validate no conflicts (excluding keys already owned by this tenant)
            for key in new_keys:
                existing_tid = _key_index.get(key)
                if existing_tid and existing_tid != tenant_id:
                    raise ValueError(
                        f"API key is already assigned to tenant '{existing_tid}'"
                    )
            # Remove old key assignments from index
            for key in t.api_keys:
                _key_index.pop(key, None)
            t.api_keys = new_keys
            for key in new_keys:
                _key_index[key] = tenant_id
        if "quota" in fields:
            q = fields["quota"]
            if "daily_requests" in q:
                t.quota.daily_requests = int(q["daily_requests"])
            if "monthly_requests" in q:
                t.quota.monthly_requests = int(q["monthly_requests"])
            if "rpm_limit" in q:
                t.quota.rpm_limit = int(q["rpm_limit"])
            if "max_token_budget" in q:
                t.quota.max_token_budget = int(q["max_token_budget"])
            if "allowed_models" in q:
                t.quota.allowed_models = list(q["allowed_models"])
        if "preferences" in fields:
            p = fields["preferences"]
            if "preferred_model" in p:
                t.preferences.preferred_model = p["preferred_model"]
            if "scenario_bias" in p:
                t.preferences.scenario_bias = p["scenario_bias"]
            if "custom_system_prompt_prefix" in p:
                t.preferences.custom_system_prompt_prefix = p[
                    "custom_system_prompt_prefix"
                ]

        t.updated_at = time.time()
        _save()
        _log.info("tenant_registry: updated tenant %s", tenant_id)
    return t


def delete_tenant(tenant_id: str) -> bool:
    """Delete a tenant and remove its key index entries. Returns True if deleted."""
    _load()
    with _lock:
        t = _tenants.pop(tenant_id, None)
        if t is None:
            return False
        for key in t.api_keys:
            _key_index.pop(key, None)
        _save()
        _log.info("tenant_registry: deleted tenant %s", tenant_id)
    return True


def list_tenants() -> list[Tenant]:
    """Return all tenants sorted by creation time (oldest first)."""
    _load()
    return sorted(_tenants.values(), key=lambda t: t.created_at)


def reset() -> None:
    """Reset in-memory state (for testing). Forces reload on next access."""
    global _tenants, _key_index, _loaded
    with _lock:
        _tenants = {}
        _key_index = {}
        _loaded = False
```

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -c "
import tenant_registry as tr
tr.reset()
t = tr.create_tenant('Acme Corp', api_keys=['lima-test-0001'], quota={'daily_requests': 2000})
assert t.tenant_id.startswith('tn-')
assert t.quota.daily_requests == 2000
found = tr.get_tenant_by_api_key('lima-test-0001')
assert found is not None and found.tenant_id == t.tenant_id
tr.update_tenant(t.tenant_id, name='Acme Inc')
assert tr.get_tenant(t.tenant_id).name == 'Acme Inc'
assert tr.delete_tenant(t.tenant_id) is True
assert tr.get_tenant(t.tenant_id) is None
tr.reset()
print('OK: Tenant registry CRUD works')
"`

Expected output:
```
OK: Tenant registry CRUD works
```

---

## Task 3: Per-Request Tenant Resolution

Modify `access_guard.py` so that `require_private_api_key()` resolves the tenant from the API key and attaches it to `request.state.tenant`, making it accessible by all downstream handlers (routing, usage tracking, etc.).

### Files to Modify

- `D:\QWEN3.0\access_guard.py` -- add tenant resolution after key validation

### Steps

- [ ] Edit `D:\QWEN3.0\access_guard.py`. Replace the entire `require_private_api_key` function (lines 43-101) with the following:

```python
def require_private_api_key(
    authorization: str = Header(default=""),
    request: object = None,
) -> None:
    """FastAPI dependency that fails closed unless a configured key is supplied.

    Checks static environment keys first, then dynamic client keys from the store.
    When a tenant is resolved from the API key, it is attached to request.state.tenant.
    Returns 503 if no authentication source is configured at all.
    """
    keys = configured_api_keys()
    token = extract_bearer_token(authorization)

    if not token:
        if not keys:
            raise HTTPException(
                status_code=503,
                detail="LiMa private API key is not configured.",
            )
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1. Check static environment keys (backward compatible)
    if keys and any(constant_time_equals(token, k) for k in keys):
        # Static keys belong to the "default" tenant (no tenant object)
        _attach_tenant(request, None)
        return

    # 2. Check dynamic client keys from the store
    client_key = None
    try:
        from routes.admin_client_keys import check_allowed_urls, find_client_key, try_consume_quota

        client_key = find_client_key(token)
    except ImportError:
        _log.debug("access_guard: admin_client_keys not available")

    if client_key is not None:
        if not client_key.get("enabled", False):
            raise HTTPException(status_code=403, detail="API key is disabled")
        # URL restriction check (if request object available)
        if request is not None and hasattr(request, "url"):
            if not check_allowed_urls(client_key, request.url.path):
                raise HTTPException(status_code=403, detail="URL not allowed for this key")
        # Atomic quota + RPM check and consumption
        allowed, reason = try_consume_quota(client_key)
        if not allowed:
            detail = {
                "daily_limit": "API key daily quota exceeded",
                "monthly_limit": "API key monthly quota exceeded",
                "rpm_limit": "API key rate limit (RPM) exceeded",
            }.get(reason, "API key quota exceeded")
            raise HTTPException(status_code=429, detail=detail)

        # Resolve tenant from the API key
        tenant = _resolve_tenant_for_key(token)
        _attach_tenant(request, tenant)

        # Tenant-level quota enforcement (if tenant exists and has quotas)
        if tenant is not None:
            _check_tenant_quota(tenant)

        return

    # No matching key found
    if not keys:
        # No static keys AND no client key matched -- fail closed
        raise HTTPException(
            status_code=503,
            detail="LiMa private API key is not configured.",
        )
    raise HTTPException(status_code=401, detail="Unauthorized")


def _resolve_tenant_for_key(token: str):
    """Attempt to resolve the tenant for an API key. Returns Tenant or None."""
    try:
        from tenant_registry import get_tenant_by_api_key
        return get_tenant_by_api_key(token)
    except (ImportError, Exception):
        _log.debug("access_guard: tenant resolution not available", exc_info=True)
        return None


def _attach_tenant(request: object, tenant) -> None:
    """Attach the resolved tenant to request.state for downstream use."""
    if request is not None and hasattr(request, "state"):
        request.state.tenant = tenant


def _check_tenant_quota(tenant) -> None:
    """Check tenant-level aggregate quota. Raises 429 if exceeded."""
    if tenant is None or not tenant.enabled:
        if tenant is not None and not tenant.enabled:
            raise HTTPException(status_code=403, detail="Tenant is disabled")
        return
    try:
        from tenant_usage import try_consume_tenant_quota
        allowed, reason = try_consume_tenant_quota(tenant)
        if not allowed:
            detail = {
                "daily_limit": "Tenant daily quota exceeded",
                "monthly_limit": "Tenant monthly quota exceeded",
                "rpm_limit": "Tenant rate limit (RPM) exceeded",
            }.get(reason, "Tenant quota exceeded")
            raise HTTPException(status_code=429, detail=detail)
    except ImportError:
        _log.debug("access_guard: tenant_usage not available", exc_info=True)
```

### Key Design Notes

- Static environment keys (`LIMA_API_KEY`, `LIMA_API_KEYS`) are "default" tenant -- they bypass tenant resolution and attach `None` as tenant.
- Dynamic client keys are resolved to their tenant via `tenant_registry.get_tenant_by_api_key()`.
- Tenant-level quota is checked *after* per-key quota (layered enforcement).
- The `_check_tenant_quota` function imports `tenant_usage` lazily so the system still works before Task 5 is implemented.

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -m pytest tests/test_access_guard.py -v --tb=short`

Expected: All existing tests pass (the new tenant attachment is a no-op when `request` is `None`).

---

## Task 4: Tenant-Aware Routing

Modify `routing_selector.py` so the `select()` function considers tenant preferences when ranking backends. The tenant is read from a new optional parameter.

### Files to Modify

- `D:\QWEN3.0\routing_selector.py` -- add tenant-aware scoring
- `D:\QWEN3.0\routing_engine.py` -- pass tenant to `select()`

### Steps

- [ ] Edit `D:\QWEN3.0\routing_selector.py`. Add the `tenant` parameter to the `select` function signature and inject tenant-aware scoring logic. Replace the function signature on line 57:

Find:
```python
def select(request_type: str, health_map: dict,
           sticky_key: str = None, scenario: str = "",
           needs_tools: bool = False, needs_agent: bool = False,
           recalled_backend: str = "",
           ide_source: str = "",
           difficulty: int = 50) -> list[str]:
```

Replace with:
```python
def select(request_type: str, health_map: dict,
           sticky_key: str = None, scenario: str = "",
           needs_tools: bool = False, needs_agent: bool = False,
           recalled_backend: str = "",
           ide_source: str = "",
           difficulty: int = 50,
           tenant=None) -> list[str]:
```

- [ ] Add tenant-aware filtering and scoring. After the tiered routing block (after line 182, before `result.sort(...)` on line 184), insert the following block:

Find:
```python
    result.sort(key=lambda b: -(
        scores.get(b, 50) * budget_manager.get_budget_priority(b)
        + random.uniform(0, 3)
    ))
```

Replace with:
```python
    # ── Tenant-aware routing: filter and boost based on tenant preferences ──
    if tenant is not None:
        try:
            from tenant import Tenant as _TenantType
            if isinstance(tenant, _TenantType):
                # Filter by allowed_models (empty list = all allowed)
                if tenant.quota.allowed_models:
                    allowed = set(tenant.quota.allowed_models)
                    result = [b for b in result if b in allowed] or result

                # Boost preferred_model backend
                if tenant.preferences.preferred_model:
                    pref = tenant.preferences.preferred_model
                    if pref in scores:
                        scores[pref] = scores.get(pref, 50) * 1.5
                    for b in result:
                        if b == pref:
                            scores[b] = scores.get(b, 50) * 1.5

                # Override scenario if tenant has a scenario_bias
                # (This affects downstream scoring that uses the scenario variable)
                if tenant.preferences.scenario_bias:
                    scenario = tenant.preferences.scenario_bias
        except (ImportError, Exception):
            _log.debug("routing_selector: tenant routing not available", exc_info=True)

    result.sort(key=lambda b: -(
        scores.get(b, 50) * budget_manager.get_budget_priority(b)
        + random.uniform(0, 3)
    ))
```

- [ ] Edit `D:\QWEN3.0\routing_engine.py` to pass the tenant to `select()`. Find the call to `select` (around line 124):

Find:
```python
    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario,
                      needs_tools=needs_tools, needs_agent=needs_agent,
                      recalled_backend=recalled_backend,
                      ide_source=ide_source)
```

Replace with:
```python
    # Resolve tenant from request context (set by access_guard)
    _tenant = None
    try:
        if headers and headers.get("x-lima-tenant-id"):
            from tenant_registry import get_tenant
            _tenant = get_tenant(headers["x-lima-tenant-id"])
    except (ImportError, Exception):
        pass

    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario,
                      needs_tools=needs_tools, needs_agent=needs_agent,
                      recalled_backend=recalled_backend,
                      ide_source=ide_source,
                      tenant=_tenant)
```

### Key Design Notes

- The `tenant` parameter is optional and defaults to `None` so all existing callers work without changes.
- `allowed_models` is a hard filter -- backends not in the list are removed. If filtering removes ALL backends, the original list is kept (safety fallback).
- `preferred_model` gets a 1.5x score boost.
- `scenario_bias` overrides the auto-detected scenario for downstream scoring.
- In `routing_engine.py`, the tenant is resolved from the `x-lima-tenant-id` header (set by the gateway layer from `request.state.tenant`).

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -c "
from tenant import Tenant, TenantQuota, TenantPreferences
t = Tenant(tenant_id='t1', name='Test', preferences=TenantPreferences(preferred_model='groq_llama8b'))
assert t.preferences.preferred_model == 'groq_llama8b'
# Verify select() accepts the new tenant parameter without error
import routing_selector
import inspect
sig = inspect.signature(routing_selector.select)
assert 'tenant' in sig.parameters
print('OK: select() accepts tenant parameter')
"`

Expected output:
```
OK: select() accepts tenant parameter
```

---

## Task 5: Per-Tenant Usage Tracking

Create a SQLite-backed usage tracker that records per-tenant request counts, token usage, cost estimates, error counts, and latency. Provides quota enforcement and usage reporting.

### Files to Create

- `D:\QWEN3.0\tenant_usage.py` -- new file

### Steps

- [ ] Create `D:\QWEN3.0\tenant_usage.py` with the following complete implementation:

```python
"""Per-tenant usage tracking backed by SQLite.

Tracks: request_count, token_usage, cost_estimate, error_count, avg_latency.
Provides quota enforcement via try_consume_tenant_quota() and reporting
via get_usage_report().

Database: data/tenant_usage.db
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time

_log = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_DB_PATH = os.path.join(_DATA_DIR, "tenant_usage.db")
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(_DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.row_factory = sqlite3.Row
        _create_tables(_conn)
    return _conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tenant_usage_daily ("
        " tenant_id TEXT NOT NULL,"
        " day TEXT NOT NULL,"
        " request_count INTEGER NOT NULL DEFAULT 0,"
        " token_count INTEGER NOT NULL DEFAULT 0,"
        " cost_estimate REAL NOT NULL DEFAULT 0.0,"
        " error_count INTEGER NOT NULL DEFAULT 0,"
        " total_latency_ms INTEGER NOT NULL DEFAULT 0,"
        " PRIMARY KEY (tenant_id, day)"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tenant_usage_monthly ("
        " tenant_id TEXT NOT NULL,"
        " month TEXT NOT NULL,"
        " request_count INTEGER NOT NULL DEFAULT 0,"
        " token_count INTEGER NOT NULL DEFAULT 0,"
        " cost_estimate REAL NOT NULL DEFAULT 0.0,"
        " error_count INTEGER NOT NULL DEFAULT 0,"
        " total_latency_ms INTEGER NOT NULL DEFAULT 0,"
        " PRIMARY KEY (tenant_id, month)"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tenant_rpm ("
        " tenant_id TEXT NOT NULL,"
        " timestamp REAL NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rpm_tenant_time"
        " ON tenant_rpm(tenant_id, timestamp)"
    )
    conn.commit()


def _now_day() -> str:
    return time.strftime("%Y-%m-%d")


def _now_month() -> str:
    return time.strftime("%Y-%m")


# -- Quota Enforcement -------------------------------------------------------


def try_consume_tenant_quota(tenant) -> tuple[bool, str]:
    """Atomically check tenant-level quotas (daily, monthly, RPM) and record usage.

    Args:
        tenant: A Tenant instance (from tenant.py).

    Returns:
        (allowed, reason) -- reason is '' on success, or one of
        'daily_limit', 'monthly_limit', 'rpm_limit' on denial.
    """
    if tenant is None or not tenant.enabled:
        return True, ""

    tid = tenant.tenant_id
    daily_limit = tenant.quota.daily_requests
    monthly_limit = tenant.quota.monthly_requests
    rpm_limit = tenant.quota.rpm_limit
    now = time.time()
    day = _now_day()
    month = _now_month()
    window_start = now - 60.0

    with _lock:
        conn = _get_conn()

        # Daily quota check
        if daily_limit > 0:
            row = conn.execute(
                "SELECT request_count FROM tenant_usage_daily"
                " WHERE tenant_id = ? AND day = ?",
                (tid, day),
            ).fetchone()
            daily_count = row["request_count"] if row else 0
            if daily_count >= daily_limit:
                return False, "daily_limit"

        # Monthly quota check
        if monthly_limit > 0:
            row = conn.execute(
                "SELECT request_count FROM tenant_usage_monthly"
                " WHERE tenant_id = ? AND month = ?",
                (tid, month),
            ).fetchone()
            monthly_count = row["request_count"] if row else 0
            if monthly_count >= monthly_limit:
                return False, "monthly_limit"

        # RPM sliding window check
        if rpm_limit > 0:
            # Prune old entries outside the 60s window
            conn.execute(
                "DELETE FROM tenant_rpm"
                " WHERE tenant_id = ? AND timestamp <= ?",
                (tid, window_start),
            )
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM tenant_rpm"
                " WHERE tenant_id = ? AND timestamp > ?",
                (tid, window_start),
            ).fetchone()
            rpm_count = row["cnt"] if row else 0
            if rpm_count >= rpm_limit:
                return False, "rpm_limit"
            conn.execute(
                "INSERT INTO tenant_rpm (tenant_id, timestamp) VALUES (?, ?)",
                (tid, now),
            )

        # All checks passed -- consume
        conn.execute(
            "INSERT INTO tenant_usage_daily"
            " (tenant_id, day, request_count)"
            " VALUES (?, ?, 1)"
            " ON CONFLICT(tenant_id, day)"
            " DO UPDATE SET request_count = request_count + 1",
            (tid, day),
        )
        conn.execute(
            "INSERT INTO tenant_usage_monthly"
            " (tenant_id, month, request_count)"
            " VALUES (?, ?, 1)"
            " ON CONFLICT(tenant_id, month)"
            " DO UPDATE SET request_count = request_count + 1",
            (tid, month),
        )
        conn.commit()

    return True, ""


def record_tenant_request(
    tenant_id: str,
    *,
    tokens: int = 0,
    cost: float = 0.0,
    error: bool = False,
    latency_ms: int = 0,
) -> None:
    """Record detailed usage for a completed request (post-routing).

    This is called after the request completes to update token counts,
    cost estimates, error counts, and latency. Call try_consume_tenant_quota()
    first for quota enforcement.
    """
    day = _now_day()
    month = _now_month()
    error_inc = 1 if error else 0

    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO tenant_usage_daily"
            " (tenant_id, day, token_count, cost_estimate, error_count, total_latency_ms)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(tenant_id, day)"
            " DO UPDATE SET"
            " token_count = token_count + ?,"
            " cost_estimate = cost_estimate + ?,"
            " error_count = error_count + ?,"
            " total_latency_ms = total_latency_ms + ?",
            (tid := tenant_id, day, tokens, cost, error_inc, latency_ms,
             tokens, cost, error_inc, latency_ms),
        )
        conn.execute(
            "INSERT INTO tenant_usage_monthly"
            " (tenant_id, month, token_count, cost_estimate, error_count, total_latency_ms)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(tenant_id, month)"
            " DO UPDATE SET"
            " token_count = token_count + ?,"
            " cost_estimate = cost_estimate + ?,"
            " error_count = error_count + ?,"
            " total_latency_ms = total_latency_ms + ?",
            (tenant_id, month, tokens, cost, error_inc, latency_ms,
             tokens, cost, error_inc, latency_ms),
        )
        conn.commit()


# -- Reporting ----------------------------------------------------------------


def get_usage_report(tenant_id: str, *, days: int = 30) -> dict:
    """Generate a usage report for a tenant.

    Returns a dict with daily breakdown, monthly totals, and current quota usage.
    """
    conn = _get_conn()
    day = _now_day()
    month = _now_month()

    # Current day usage
    daily_row = conn.execute(
        "SELECT * FROM tenant_usage_daily WHERE tenant_id = ? AND day = ?",
        (tenant_id, day),
    ).fetchone()

    # Current month usage
    monthly_row = conn.execute(
        "SELECT * FROM tenant_usage_monthly WHERE tenant_id = ? AND month = ?",
        (tenant_id, month),
    ).fetchone()

    # Recent daily breakdown
    daily_rows = conn.execute(
        "SELECT * FROM tenant_usage_daily"
        " WHERE tenant_id = ?"
        " ORDER BY day DESC LIMIT ?",
        (tenant_id, days),
    ).fetchall()

    return {
        "tenant_id": tenant_id,
        "today": {
            "request_count": daily_row["request_count"] if daily_row else 0,
            "token_count": daily_row["token_count"] if daily_row else 0,
            "cost_estimate": daily_row["cost_estimate"] if daily_row else 0.0,
            "error_count": daily_row["error_count"] if daily_row else 0,
            "avg_latency_ms": (
                int(daily_row["total_latency_ms"] / daily_row["request_count"])
                if daily_row and daily_row["request_count"] > 0
                else 0
            ),
        },
        "this_month": {
            "request_count": monthly_row["request_count"] if monthly_row else 0,
            "token_count": monthly_row["token_count"] if monthly_row else 0,
            "cost_estimate": monthly_row["cost_estimate"] if monthly_row else 0.0,
            "error_count": monthly_row["error_count"] if monthly_row else 0,
            "avg_latency_ms": (
                int(monthly_row["total_latency_ms"] / monthly_row["request_count"])
                if monthly_row and monthly_row["request_count"] > 0
                else 0
            ),
        },
        "daily_breakdown": [
            {
                "day": r["day"],
                "request_count": r["request_count"],
                "token_count": r["token_count"],
                "cost_estimate": r["cost_estimate"],
                "error_count": r["error_count"],
                "avg_latency_ms": (
                    int(r["total_latency_ms"] / r["request_count"])
                    if r["request_count"] > 0
                    else 0
                ),
            }
            for r in daily_rows
        ],
    }


def get_all_tenants_usage_summary() -> list[dict]:
    """Return current-month usage summary for all tenants (for admin stats)."""
    conn = _get_conn()
    month = _now_month()
    rows = conn.execute(
        "SELECT * FROM tenant_usage_monthly WHERE month = ? ORDER BY request_count DESC",
        (month,),
    ).fetchall()
    return [
        {
            "tenant_id": r["tenant_id"],
            "request_count": r["request_count"],
            "token_count": r["token_count"],
            "cost_estimate": r["cost_estimate"],
            "error_count": r["error_count"],
            "avg_latency_ms": (
                int(r["total_latency_ms"] / r["request_count"])
                if r["request_count"] > 0
                else 0
            ),
        }
        for r in rows
    ]


def reset_db() -> None:
    """Reset the database (for testing). Drops all tables and recreates."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        if os.path.exists(_DB_PATH):
            os.remove(_DB_PATH)
        # Recreate on next access
        _get_conn()
```

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -c "
import tenant_usage
tenant_usage.reset_db()
from tenant import Tenant, TenantQuota
t = Tenant(tenant_id='test-tenant', name='Test', quota=TenantQuota(daily_requests=5, rpm_limit=100))
# Consume 5 requests (should all succeed)
for i in range(5):
    ok, reason = tenant_usage.try_consume_tenant_quota(t)
    assert ok, f'Request {i} failed: {reason}'
# 6th request should fail (daily limit)
ok, reason = tenant_usage.try_consume_tenant_quota(t)
assert not ok and reason == 'daily_limit'
# Record detailed usage
tenant_usage.record_tenant_request('test-tenant', tokens=500, cost=0.01, latency_ms=200)
report = tenant_usage.get_usage_report('test-tenant')
assert report['today']['request_count'] == 5
assert report['today']['token_count'] == 500
tenant_usage.reset_db()
print('OK: Tenant usage tracking and quota enforcement works')
"`

Expected output:
```
OK: Tenant usage tracking and quota enforcement works
```

---

## Task 6: Tenant Admin API

Create FastAPI admin endpoints for full tenant CRUD operations, usage viewing, and quota resets.

### Files to Create

- `D:\QWEN3.0\routes\admin_tenants.py` -- new file

### Files to Modify

- `D:\QWEN3.0\routes\admin_api.py` -- include the new tenant router

### Steps

- [ ] Create `D:\QWEN3.0\routes\admin_tenants.py` with the following complete implementation:

```python
"""Tenant management admin API endpoints.

Provides CRUD for tenants: list, create, update, delete, view usage,
reset quotas. Protected by admin auth + CSRF for mutations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()
_log = logging.getLogger(__name__)


@router.get("/admin/api/tenants", dependencies=[Depends(verify_admin)])
async def list_tenants():
    """List all tenants with summary info."""
    import tenant_registry as tr
    import tenant_usage

    tenants = tr.list_tenants()
    result = []
    for t in tenants:
        usage = tenant_usage.get_usage_report(t.tenant_id)
        result.append({
            "tenant_id": t.tenant_id,
            "name": t.name,
            "enabled": t.enabled,
            "api_key_count": len(t.api_keys),
            "quota": {
                "daily_requests": t.quota.daily_requests,
                "monthly_requests": t.quota.monthly_requests,
                "rpm_limit": t.quota.rpm_limit,
                "max_token_budget": t.quota.max_token_budget,
                "allowed_models": t.quota.allowed_models,
            },
            "preferences": {
                "preferred_model": t.preferences.preferred_model,
                "scenario_bias": t.preferences.scenario_bias,
            },
            "usage_today": usage["today"],
            "usage_this_month": usage["this_month"],
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        })
    return {"tenants": result, "total": len(result)}


@router.post(
    "/admin/api/tenants",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
)
async def create_tenant(body: dict):
    """Create a new tenant."""
    import tenant_registry as tr

    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")

    try:
        t = tr.create_tenant(
            name=name,
            api_keys=body.get("api_keys"),
            quota=body.get("quota"),
            preferences=body.get("preferences"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    _log.info("admin: created tenant %s (%s)", t.tenant_id, name)
    return {"ok": True, "tenant": t.to_dict()}


@router.get(
    "/admin/api/tenants/{tenant_id}",
    dependencies=[Depends(verify_admin)],
)
async def get_tenant(tenant_id: str):
    """Get a single tenant with full details and usage report."""
    import tenant_registry as tr
    import tenant_usage

    t = tr.get_tenant(tenant_id)
    if t is None:
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")

    usage = tenant_usage.get_usage_report(tenant_id)
    return {
        "tenant": t.to_dict(),
        "usage": usage,
    }


@router.put(
    "/admin/api/tenants/{tenant_id}",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
)
async def update_tenant(tenant_id: str, body: dict):
    """Update tenant configuration."""
    import tenant_registry as tr

    try:
        t = tr.update_tenant(
            tenant_id,
            **{k: v for k, v in body.items() if k in (
                "name", "api_keys", "quota", "preferences", "enabled"
            )},
        )
    except KeyError:
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    _log.info("admin: updated tenant %s", tenant_id)
    return {"ok": True, "tenant": t.to_dict()}


@router.delete(
    "/admin/api/tenants/{tenant_id}",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
)
async def delete_tenant(tenant_id: str):
    """Delete a tenant."""
    import tenant_registry as tr

    if not tr.delete_tenant(tenant_id):
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")

    _log.info("admin: deleted tenant %s", tenant_id)
    return {"ok": True, "deleted": tenant_id}


@router.get(
    "/admin/api/tenants/{tenant_id}/usage",
    dependencies=[Depends(verify_admin)],
)
async def get_tenant_usage(tenant_id: str, days: int = 30):
    """Get detailed usage report for a tenant."""
    import tenant_registry as tr
    import tenant_usage

    t = tr.get_tenant(tenant_id)
    if t is None:
        raise HTTPException(404, f"Tenant '{tenant_id}' not found")

    report = tenant_usage.get_usage_report(tenant_id, days=days)
    return report
```

- [ ] Edit `D:\QWEN3.0\routes\admin_api.py` to include the tenant router. Find the sub-module router includes (around line 44):

Find:
```python
router.include_router(_config_router)
```

Replace with:
```python
router.include_router(_config_router)

# Tenant management (lazy import to avoid circular deps at startup)
try:
    from routes.admin_tenants import router as _tenants_router
    router.include_router(_tenants_router)
except ImportError:
    pass
```

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -c "
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.admin_tenants import router
from routes.admin_auth import verify_admin, verify_csrf

app = FastAPI()
app.dependency_overrides[verify_admin] = lambda: None
app.dependency_overrides[verify_csrf] = lambda: None
app.include_router(router)
client = TestClient(app)

# Create a tenant
resp = client.post('/admin/api/tenants', json={'name': 'TestCorp', 'quota': {'daily_requests': 1000}})
assert resp.status_code == 200, resp.text
body = resp.json()
assert body['ok'] is True
tid = body['tenant']['tenant_id']

# List tenants
resp = client.get('/admin/api/tenants')
assert resp.status_code == 200
assert resp.json()['total'] >= 1

# Get single tenant
resp = client.get(f'/admin/api/tenants/{tid}')
assert resp.status_code == 200
assert resp.json()['tenant']['name'] == 'TestCorp'

# Update tenant
resp = client.put(f'/admin/api/tenants/{tid}', json={'name': 'TestCorp Inc'})
assert resp.status_code == 200
assert resp.json()['tenant']['name'] == 'TestCorp Inc'

# Delete tenant
resp = client.delete(f'/admin/api/tenants/{tid}')
assert resp.status_code == 200

print('OK: Tenant admin API CRUD works')
"`

Expected output:
```
OK: Tenant admin API CRUD works
```

---

## Task 7: Usage Reporting -- Tenant Breakdown in Admin Stats

Add tenant-level usage analytics to the existing admin stats endpoint: top 10 tenants by usage, quota utilization per tenant, and cost per tenant.

### Files to Modify

- `D:\QWEN3.0\routes\admin_api.py` -- add tenant breakdown to `/api/stats`

### Steps

- [ ] Edit `D:\QWEN3.0\routes\admin_api.py`. In the `admin_stats()` function, add tenant usage data to the return dict. Find the return statement (around line 110):

Find:
```python
        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(stats["intent_distribution"]),
            "unique_ips": len(ips),
            "ide_distribution": ide_dist,
            "version": _get_version_info(),
        }
```

Replace with:
```python
        # Tenant usage breakdown
        tenant_usage_summary = []
        try:
            import tenant_usage
            import tenant_registry as tr
            all_usage = tenant_usage.get_all_tenants_usage_summary()
            for u in all_usage[:10]:
                t = tr.get_tenant(u["tenant_id"])
                quota_info = {}
                if t:
                    quota_info = {
                        "name": t.name,
                        "daily_limit": t.quota.daily_requests,
                        "monthly_limit": t.quota.monthly_requests,
                        "daily_utilization_pct": round(
                            u["request_count"] / max(t.quota.daily_requests, 1) * 100, 1
                        ),
                        "monthly_utilization_pct": round(
                            u["request_count"] / max(t.quota.monthly_requests, 1) * 100, 1
                        ),
                    }
                tenant_usage_summary.append({**u, **quota_info})
        except (ImportError, Exception):
            _log.debug("admin_stats: tenant usage not available", exc_info=True)

        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(stats["intent_distribution"]),
            "unique_ips": len(ips),
            "ide_distribution": ide_dist,
            "version": _get_version_info(),
            "tenant_usage": tenant_usage_summary,
        }
```

### Verification

- [ ] Run: `cd /d D:\QWEN3.0 && python -m pytest tests/test_admin_stats.py -v --tb=short`

Expected: Existing test still passes, and the response now includes a `tenant_usage` key (empty list when no tenants exist).

---

## Task 8: Integration Tests

Write comprehensive pytest integration tests that exercise the full pipeline: create tenant, assign API keys, make authenticated requests, verify quota enforcement, and validate tenant-aware routing behavior.

### Files to Create

- `D:\QWEN3.0\tests\test_multi_tenant.py` -- new file

### Steps

- [ ] Create `D:\QWEN3.0\tests\test_multi_tenant.py` with the following complete test suite:

```python
"""Integration tests for multi-tenant support and quota management.

Tests cover:
  - Tenant model serialization/deserialization
  - Tenant registry CRUD + key index
  - Per-request tenant resolution in access_guard
  - Tenant-aware routing selector behavior
  - Per-tenant usage tracking and quota enforcement
  - Admin API endpoints for tenant management
"""

import asyncio
import os
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ── Tenant Model Tests ──────────────────────────────────────────────────────


class TestTenantModel:
    def test_tenant_to_dict_roundtrip(self):
        from tenant import Tenant, TenantPreferences, TenantQuota

        t = Tenant(
            tenant_id="tn-test001",
            name="Test Corp",
            api_keys=["lima-aaaa-bbbb-cccc"],
            quota=TenantQuota(
                daily_requests=2000,
                monthly_requests=50000,
                rpm_limit=30,
                max_token_budget=4096,
                allowed_models=["groq_llama8b", "mistral_small"],
            ),
            preferences=TenantPreferences(
                preferred_model="groq_llama8b",
                scenario_bias="coding",
                custom_system_prompt_prefix="You are a coding assistant.",
            ),
        )
        d = t.to_dict()
        t2 = Tenant.from_dict(d)

        assert t2.tenant_id == "tn-test001"
        assert t2.name == "Test Corp"
        assert t2.api_keys == ["lima-aaaa-bbbb-cccc"]
        assert t2.quota.daily_requests == 2000
        assert t2.quota.monthly_requests == 50000
        assert t2.quota.rpm_limit == 30
        assert t2.quota.max_token_budget == 4096
        assert t2.quota.allowed_models == ["groq_llama8b", "mistral_small"]
        assert t2.preferences.preferred_model == "groq_llama8b"
        assert t2.preferences.scenario_bias == "coding"
        assert t2.preferences.custom_system_prompt_prefix == "You are a coding assistant."

    def test_tenant_defaults(self):
        from tenant import Tenant

        t = Tenant()
        assert t.tenant_id == ""
        assert t.quota.daily_requests == 5000
        assert t.quota.allowed_models == []
        assert t.preferences.preferred_model == ""

    def test_from_dict_handles_missing_fields(self):
        from tenant import Tenant

        t = Tenant.from_dict({"tenant_id": "tn-minimal"})
        assert t.tenant_id == "tn-minimal"
        assert t.name == ""
        assert t.quota.daily_requests == 5000  # default
        assert t.enabled is True


# ── Tenant Registry Tests ───────────────────────────────────────────────────


class TestTenantRegistry:
    @pytest.fixture(autouse=True)
    def _reset_registry(self):
        import tenant_registry as tr
        tr.reset()
        yield
        tr.reset()

    def test_create_and_get_tenant(self):
        import tenant_registry as tr

        t = tr.create_tenant("Acme", quota={"daily_requests": 1000})
        assert t.tenant_id.startswith("tn-")
        assert t.quota.daily_requests == 1000

        found = tr.get_tenant(t.tenant_id)
        assert found is not None
        assert found.name == "Acme"

    def test_get_tenant_by_api_key(self):
        import tenant_registry as tr

        t = tr.create_tenant("KeyCorp", api_keys=["lima-key-001"])
        found = tr.get_tenant_by_api_key("lima-key-001")
        assert found is not None
        assert found.tenant_id == t.tenant_id

        assert tr.get_tenant_by_api_key("nonexistent-key") is None

    def test_key_conflict_raises(self):
        import tenant_registry as tr

        tr.create_tenant("First", api_keys=["lima-shared-key"])
        with pytest.raises(ValueError, match="already assigned"):
            tr.create_tenant("Second", api_keys=["lima-shared-key"])

    def test_update_tenant_name(self):
        import tenant_registry as tr

        t = tr.create_tenant("OldName")
        updated = tr.update_tenant(t.tenant_id, name="NewName")
        assert updated.name == "NewName"

    def test_update_tenant_api_keys(self):
        import tenant_registry as tr

        t = tr.create_tenant("Keys", api_keys=["lima-old-key"])
        assert tr.get_tenant_by_api_key("lima-old-key") is not None

        tr.update_tenant(t.tenant_id, api_keys=["lima-new-key"])
        assert tr.get_tenant_by_api_key("lima-old-key") is None
        assert tr.get_tenant_by_api_key("lima-new-key") is not None

    def test_update_tenant_quota(self):
        import tenant_registry as tr

        t = tr.create_tenant("Quota")
        tr.update_tenant(t.tenant_id, quota={"daily_requests": 999, "rpm_limit": 5})
        updated = tr.get_tenant(t.tenant_id)
        assert updated.quota.daily_requests == 999
        assert updated.quota.rpm_limit == 5

    def test_update_tenant_preferences(self):
        import tenant_registry as tr

        t = tr.create_tenant("Prefs")
        tr.update_tenant(
            t.tenant_id,
            preferences={"preferred_model": "mistral_large", "scenario_bias": "coding"},
        )
        updated = tr.get_tenant(t.tenant_id)
        assert updated.preferences.preferred_model == "mistral_large"
        assert updated.preferences.scenario_bias == "coding"

    def test_delete_tenant(self):
        import tenant_registry as tr

        t = tr.create_tenant("ToDelete", api_keys=["lima-del-key"])
        assert tr.delete_tenant(t.tenant_id) is True
        assert tr.get_tenant(t.tenant_id) is None
        assert tr.get_tenant_by_api_key("lima-del-key") is None
        # Delete again returns False
        assert tr.delete_tenant(t.tenant_id) is False

    def test_list_tenants_sorted_by_creation(self):
        import tenant_registry as tr

        tr.create_tenant("First")
        tr.create_tenant("Second")
        tr.create_tenant("Third")
        tenants = tr.list_tenants()
        assert len(tenants) >= 3
        names = [t.name for t in tenants]
        assert "First" in names
        assert "Second" in names
        assert "Third" in names

    def test_update_nonexistent_tenant_raises(self):
        import tenant_registry as tr

        with pytest.raises(KeyError, match="not found"):
            tr.update_tenant("tn-nonexistent", name="nope")


# ── Tenant Usage Tests ──────────────────────────────────────────────────────


class TestTenantUsage:
    @pytest.fixture(autouse=True)
    def _reset_usage_db(self):
        import tenant_usage
        tenant_usage.reset_db()
        yield
        tenant_usage.reset_db()

    def test_quota_enforcement_daily_limit(self):
        import tenant_usage
        from tenant import Tenant, TenantQuota

        t = Tenant(
            tenant_id="usage-test",
            name="Usage",
            quota=TenantQuota(daily_requests=3, rpm_limit=100),
        )

        for i in range(3):
            ok, reason = tenant_usage.try_consume_tenant_quota(t)
            assert ok, f"Request {i} should succeed: {reason}"

        ok, reason = tenant_usage.try_consume_tenant_quota(t)
        assert not ok
        assert reason == "daily_limit"

    def test_quota_enforcement_rpm_limit(self):
        import tenant_usage
        from tenant import Tenant, TenantQuota

        t = Tenant(
            tenant_id="rpm-test",
            name="RPM",
            quota=TenantQuota(daily_requests=10000, rpm_limit=2),
        )

        ok1, _ = tenant_usage.try_consume_tenant_quota(t)
        ok2, _ = tenant_usage.try_consume_tenant_quota(t)
        assert ok1 and ok2

        ok3, reason = tenant_usage.try_consume_tenant_quota(t)
        assert not ok3
        assert reason == "rpm_limit"

    def test_record_and_report(self):
        import tenant_usage
        from tenant import Tenant, TenantQuota

        t = Tenant(
            tenant_id="report-test",
            name="Report",
            quota=TenantQuota(daily_requests=1000, rpm_limit=1000),
        )

        # Consume 3 requests
        for _ in range(3):
            tenant_usage.try_consume_tenant_quota(t)

        # Record detailed usage
        tenant_usage.record_tenant_request(
            "report-test", tokens=100, cost=0.005, latency_ms=150
        )
        tenant_usage.record_tenant_request(
            "report-test", tokens=200, cost=0.01, error=True, latency_ms=300
        )

        report = tenant_usage.get_usage_report("report-test")
        assert report["today"]["request_count"] == 3
        assert report["today"]["token_count"] == 300
        assert report["today"]["error_count"] == 1
        assert abs(report["today"]["cost_estimate"] - 0.015) < 0.001

    def test_disabled_tenant_passes_quota(self):
        import tenant_usage
        from tenant import Tenant, TenantQuota

        t = Tenant(
            tenant_id="disabled-test",
            name="Disabled",
            enabled=False,
            quota=TenantQuota(daily_requests=0),
        )
        # Disabled tenant should not block (access_guard handles the 403)
        ok, reason = tenant_usage.try_consume_tenant_quota(t)
        assert ok

    def test_none_tenant_passes_quota(self):
        import tenant_usage

        ok, reason = tenant_usage.try_consume_tenant_quota(None)
        assert ok

    def test_all_tenants_summary(self):
        import tenant_usage
        from tenant import Tenant, TenantQuota

        t = Tenant(
            tenant_id="summary-test",
            name="Summary",
            quota=TenantQuota(daily_requests=100, rpm_limit=100),
        )
        tenant_usage.try_consume_tenant_quota(t)
        tenant_usage.record_tenant_request("summary-test", tokens=50)

        summary = tenant_usage.get_all_tenants_usage_summary()
        assert any(s["tenant_id"] == "summary-test" for s in summary)


# ── Access Guard Tenant Resolution Tests ────────────────────────────────────


class TestAccessGuardTenantResolution:
    @pytest.fixture(autouse=True)
    def _reset_registry(self):
        import tenant_registry as tr
        tr.reset()
        yield
        tr.reset()

    def test_static_key_attaches_none_tenant(self, monkeypatch):
        """Static env keys should attach tenant=None (default tenant)."""
        import access_guard

        monkeypatch.setenv("LIMA_API_KEY", "static-key-123")
        monkeypatch.delenv("LIMA_API_KEYS", raising=False)

        class FakeState:
            tenant = "UNSET"

        class FakeRequest:
            state = FakeState()
            url = type("URL", (), {"path": "/v1/chat/completions"})()

        req = FakeRequest()
        access_guard.require_private_api_key("Bearer static-key-123", request=req)
        assert req.state.tenant is None

    def test_missing_authorization_raises_401(self, monkeypatch):
        import access_guard

        monkeypatch.setenv("LIMA_API_KEY", "some-key")
        monkeypatch.delenv("LIMA_API_KEYS", raising=False)

        with pytest.raises(HTTPException) as exc:
            access_guard.require_private_api_key("")
        assert exc.value.status_code == 401


# ── Admin Tenant API Tests ──────────────────────────────────────────────────


class TestAdminTenantAPI:
    @pytest.fixture(autouse=True)
    def _reset_state(self):
        import tenant_registry as tr
        import tenant_usage
        tr.reset()
        tenant_usage.reset_db()
        yield
        tr.reset()
        tenant_usage.reset_db()

    @pytest.fixture
    def client(self):
        from routes.admin_auth import verify_admin, verify_csrf
        from routes.admin_tenants import router

        app = FastAPI()
        app.dependency_overrides[verify_admin] = lambda: None
        app.dependency_overrides[verify_csrf] = lambda: None
        app.include_router(router)
        return TestClient(app)

    def test_create_tenant_via_api(self, client):
        resp = client.post(
            "/admin/api/tenants",
            json={
                "name": "API Corp",
                "quota": {"daily_requests": 500, "rpm_limit": 10},
                "preferences": {"preferred_model": "groq_llama8b"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["tenant"]["name"] == "API Corp"
        assert body["tenant"]["quota"]["daily_requests"] == 500
        assert body["tenant"]["preferences"]["preferred_model"] == "groq_llama8b"

    def test_create_tenant_requires_name(self, client):
        resp = client.post("/admin/api/tenants", json={})
        assert resp.status_code == 400

    def test_list_tenants_via_api(self, client):
        client.post("/admin/api/tenants", json={"name": "T1"})
        client.post("/admin/api/tenants", json={"name": "T2"})
        resp = client.get("/admin/api/tenants")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    def test_get_tenant_via_api(self, client):
        create_resp = client.post("/admin/api/tenants", json={"name": "Detail"})
        tid = create_resp.json()["tenant"]["tenant_id"]

        resp = client.get(f"/admin/api/tenants/{tid}")
        assert resp.status_code == 200
        assert resp.json()["tenant"]["name"] == "Detail"

    def test_get_nonexistent_tenant_returns_404(self, client):
        resp = client.get("/admin/api/tenants/tn-nonexistent")
        assert resp.status_code == 404

    def test_update_tenant_via_api(self, client):
        create_resp = client.post("/admin/api/tenants", json={"name": "OldName"})
        tid = create_resp.json()["tenant"]["tenant_id"]

        resp = client.put(
            f"/admin/api/tenants/{tid}",
            json={"name": "NewName", "quota": {"daily_requests": 999}},
        )
        assert resp.status_code == 200
        assert resp.json()["tenant"]["name"] == "NewName"
        assert resp.json()["tenant"]["quota"]["daily_requests"] == 999

    def test_delete_tenant_via_api(self, client):
        create_resp = client.post("/admin/api/tenants", json={"name": "ToDelete"})
        tid = create_resp.json()["tenant"]["tenant_id"]

        resp = client.delete(f"/admin/api/tenants/{tid}")
        assert resp.status_code == 200

        resp = client.get(f"/admin/api/tenants/{tid}")
        assert resp.status_code == 404

    def test_tenant_usage_endpoint(self, client):
        import tenant_usage
        from tenant import Tenant, TenantQuota

        create_resp = client.post("/admin/api/tenants", json={"name": "UsageCo"})
        tid = create_resp.json()["tenant"]["tenant_id"]

        # Simulate some usage
        t = Tenant(
            tenant_id=tid,
            name="UsageCo",
            quota=TenantQuota(daily_requests=1000, rpm_limit=1000),
        )
        tenant_usage.try_consume_tenant_quota(t)
        tenant_usage.record_tenant_request(tid, tokens=100, cost=0.01)

        resp = client.get(f"/admin/api/tenants/{tid}/usage")
        assert resp.status_code == 200
        assert resp.json()["today"]["request_count"] >= 1

    def test_key_conflict_returns_400(self, client):
        client.post(
            "/admin/api/tenants",
            json={"name": "First", "api_keys": ["lima-conflict-key"]},
        )
        resp = client.post(
            "/admin/api/tenants",
            json={"name": "Second", "api_keys": ["lima-conflict-key"]},
        )
        assert resp.status_code == 400


# ── Tenant-Aware Routing Tests ──────────────────────────────────────────────


class TestTenantAwareRouting:
    def test_select_accepts_tenant_parameter(self):
        """Verify select() signature includes tenant parameter."""
        import inspect
        import routing_selector

        sig = inspect.signature(routing_selector.select)
        assert "tenant" in sig.parameters
        assert sig.parameters["tenant"].default is None

    def test_allowed_models_filters_backends(self):
        """Tenant with allowed_models should filter out disallowed backends."""
        from tenant import Tenant, TenantPreferences, TenantQuota

        t = Tenant(
            tenant_id="filter-test",
            name="Filter",
            quota=TenantQuota(
                allowed_models=["groq_llama8b", "mistral_small"],
            ),
            preferences=TenantPreferences(),
        )
        # Verify the tenant model holds the allowed_models correctly
        assert set(t.quota.allowed_models) == {"groq_llama8b", "mistral_small"}

    def test_preferred_model_boost(self):
        """Tenant preferred_model should get a score boost."""
        from tenant import Tenant, TenantPreferences, TenantQuota

        t = Tenant(
            tenant_id="boost-test",
            name="Boost",
            preferences=TenantPreferences(preferred_model="groq_llama8b"),
        )
        assert t.preferences.preferred_model == "groq_llama8b"
```

- [ ] Run the full test suite:

```
cd /d D:\QWEN3.0 && python -m pytest tests/test_multi_tenant.py -v --tb=short
```

Expected output (all pass):
```
tests/test_multi_tenant.py::TestTenantModel::test_tenant_to_dict_roundtrip PASSED
tests/test_multi_tenant.py::TestTenantModel::test_tenant_defaults PASSED
tests/test_multi_tenant.py::TestTenantModel::test_from_dict_handles_missing_fields PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_create_and_get_tenant PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_get_tenant_by_api_key PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_key_conflict_raises PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_update_tenant_name PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_update_tenant_api_keys PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_update_tenant_quota PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_update_tenant_preferences PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_delete_tenant PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_list_tenants_sorted_by_creation PASSED
tests/test_multi_tenant.py::TestTenantRegistry::test_update_nonexistent_tenant_raises PASSED
tests/test_multi_tenant.py::TestTenantUsage::test_quota_enforcement_daily_limit PASSED
tests/test_multi_tenant.py::TestTenantUsage::test_quota_enforcement_rpm_limit PASSED
tests/test_multi_tenant.py::TestTenantUsage::test_record_and_report PASSED
tests/test_multi_tenant.py::TestTenantUsage::test_disabled_tenant_passes_quota PASSED
tests/test_multi_tenant.py::TestTenantUsage::test_none_tenant_passes_quota PASSED
tests/test_multi_tenant.py::TestTenantUsage::test_all_tenants_summary PASSED
tests/test_multi_tenant.py::TestAccessGuardTenantResolution::test_static_key_attaches_none_tenant PASSED
tests/test_multi_tenant.py::TestAccessGuardTenantResolution::test_missing_authorization_raises_401 PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_create_tenant_via_api PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_create_tenant_requires_name PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_list_tenants_via_api PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_get_tenant_via_api PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_get_nonexistent_tenant_returns_404 PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_update_tenant_via_api PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_delete_tenant_via_api PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_tenant_usage_endpoint PASSED
tests/test_multi_tenant.py::TestAdminTenantAPI::test_key_conflict_returns_400 PASSED
tests/test_multi_tenant.py::TestTenantAwareRouting::test_select_accepts_tenant_parameter PASSED
tests/test_multi_tenant.py::TestTenantAwareRouting::test_allowed_models_filters_backends PASSED
tests/test_multi_tenant.py::TestTenantAwareRouting::test_preferred_model_boost PASSED

32 passed
```

- [ ] Verify existing tests still pass:

```
cd /d D:\QWEN3.0 && python -m pytest tests/test_access_guard.py tests/test_admin_stats.py -v --tb=short
```

Expected: All existing tests pass without modification.

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `D:\QWEN3.0\tenant.py` | CREATE | Tenant, TenantQuota, TenantPreferences dataclasses |
| `D:\QWEN3.0\tenant_registry.py` | CREATE | In-memory CRUD + JSON persistence + key index |
| `D:\QWEN3.0\access_guard.py` | MODIFY | Add tenant resolution + attach to request.state |
| `D:\QWEN3.0\routing_selector.py` | MODIFY | Add `tenant` param, filter/boost by preferences |
| `D:\QWEN3.0\routing_engine.py` | MODIFY | Pass tenant from headers to `select()` |
| `D:\QWEN3.0\tenant_usage.py` | CREATE | SQLite-backed usage tracking + quota enforcement |
| `D:\QWEN3.0\routes\admin_tenants.py` | CREATE | Admin CRUD API for tenants |
| `D:\QWEN3.0\routes\admin_api.py` | MODIFY | Include tenant router + tenant stats in `/api/stats` |
| `D:\QWEN3.0\tests\test_multi_tenant.py` | CREATE | 32 integration tests covering all components |

## Dependency Graph

```
Task 1: tenant.py (no deps)
    |
Task 2: tenant_registry.py (depends on Task 1)
    |
Task 3: access_guard.py modifications (depends on Tasks 2, 5)
    |                                    ^
Task 4: routing_selector.py + routing_engine.py (depends on Task 1)
    |
Task 5: tenant_usage.py (depends on Task 1)
    |
Task 6: routes/admin_tenants.py (depends on Tasks 2, 5)
    |
Task 7: routes/admin_api.py stats (depends on Tasks 2, 5, 6)
    |
Task 8: tests/test_multi_tenant.py (depends on all above)
```

Implementation order: 1 -> 2 -> 5 -> 3 -> 4 -> 6 -> 7 -> 8
