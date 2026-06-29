"""Redis CAS (compare-and-swap) helpers for device task state (AUDIT-9-S4).

Provides atomic compare-and-swap on the task state JSON blob stored in the
``lima:device:tasks`` hash, plus an atomic events-append that avoids the
lost-update problem when concurrent writers each read the events list, append
locally, and overwrite the whole blob.

Both helpers use Lua scripts evaluated via ``register_script`` so the read +
compare + write happens atomically inside Redis.
"""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.redis_store_helpers import decode_redis_json, encode_redis_json

_log = logging.getLogger(__name__)

VERSION_FIELD = "_version"


# Lua: atomic compare-and-swap on a single hash field holding a JSON blob.
# KEYS[1] = tasks hash key
# ARGV[1] = task_id (hash field)
# ARGV[2] = expected_version (integer; -1 = create-only when absent)
# ARGV[3] = new_json (full state JSON to write)
# ARGV[4] = ttl_seconds (for EXPIRE)
# Returns: 1 success, 0 version mismatch, 2 missing when expected>=0
_CAS_LUA = """
local cur = redis.call('HGET', KEYS[1], ARGV[1])
if cur == false or cur == nil then
    if tonumber(ARGV[2]) < 0 then
        redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
        redis.call('EXPIRE', KEYS[1], ARGV[4])
        return 1
    end
    return 2
end
local state = cjson.decode(cur)
local cur_version = tonumber(state['_version']) or 0
if cur_version ~= tonumber(ARGV[2]) then
    return 0
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 1
"""

# Lua: atomic append to events list inside the state JSON blob.
# Decodes the blob, appends the event, bumps version, encodes, writes back —
# all atomically. Avoids the lost-append problem.
# KEYS[1] = tasks hash key
# ARGV[1] = task_id (hash field)
# ARGV[2] = event_json (the single event to append)
# ARGV[3] = status (new status to set, empty string = leave unchanged)
# ARGV[4] = ttl_seconds
# Returns: updated state JSON (string), or nil if task missing
_APPEND_EVENT_LUA = """
local cur = redis.call('HGET', KEYS[1], ARGV[1])
if cur == false or cur == nil then
    return nil
end
local state = cjson.decode(cur)
local events = state['events']
if events == nil then
    events = {}
    state['events'] = events
end
local evt = cjson.decode(ARGV[2])
table.insert(events, evt)
if ARGV[3] ~= '' then
    state['status'] = ARGV[3]
end
local ver = tonumber(state['_version']) or 0
state['_version'] = ver + 1
local out = cjson.encode(state)
redis.call('HSET', KEYS[1], ARGV[1], out)
redis.call('EXPIRE', KEYS[1], ARGV[4])
return out
"""

# Lazily registered script objects (keyed by id(redis_client) to support tests).
_cas_scripts: dict[int, Any] = {}
_append_scripts: dict[int, Any] = {}


def _get_cas_script(redis_client):
    cid = id(redis_client)
    script = _cas_scripts.get(cid)
    if script is None:
        script = redis_client.register_script(_CAS_LUA)
        _cas_scripts[cid] = script
    return script


def _get_append_script(redis_client):
    cid = id(redis_client)
    script = _append_scripts.get(cid)
    if script is None:
        script = redis_client.register_script(_APPEND_EVENT_LUA)
        _append_scripts[cid] = script
    return script


def reset_script_cache_for_tests() -> None:
    """Drop cached Lua scripts so a fresh FakeRedis gets re-registered."""
    _cas_scripts.clear()
    _append_scripts.clear()


def cas_write_state(
    redis_client,
    tasks_key: str,
    task_id: str,
    new_state: dict[str, Any],
    expected_version: int,
    ttl_seconds: int,
) -> bool:
    """Atomically write ``new_state`` only if the stored ``_version`` matches.

    Returns True on success, False on version mismatch or missing-when-exists.
    The caller must bump ``_version`` inside ``new_state`` before calling.

    Falls back to a non-atomic Python implementation when the client does not
    support ``register_script`` (e.g. test fakes) — acceptable in single-threaded
    test contexts where there is no real concurrency.
    """
    if VERSION_FIELD not in new_state:
        new_state[VERSION_FIELD] = max(0, expected_version) + 1
    if not hasattr(redis_client, "register_script"):
        return _cas_write_fallback(redis_client, tasks_key, task_id, new_state, expected_version, ttl_seconds)
    script = _get_cas_script(redis_client)
    result = script(keys=[tasks_key], args=[task_id, expected_version, encode_redis_json(new_state), ttl_seconds])
    return result == 1


def _cas_write_fallback(redis_client, tasks_key, task_id, new_state, expected_version, ttl_seconds) -> bool:
    """Non-atomic CAS fallback for Redis clients without Lua support (test fakes)."""
    cur = redis_client.hget(tasks_key, task_id)
    if cur is None:
        if expected_version < 0:
            redis_client.hset(tasks_key, task_id, encode_redis_json(new_state))
            redis_client.expire(tasks_key, ttl_seconds)
            return True
        return False
    state = decode_redis_json(cur)
    if int(state.get(VERSION_FIELD, 0)) != expected_version:
        return False
    redis_client.hset(tasks_key, task_id, encode_redis_json(new_state))
    redis_client.expire(tasks_key, ttl_seconds)
    return True


def append_event_atomic(
    redis_client,
    tasks_key: str,
    task_id: str,
    event: dict[str, Any],
    ttl_seconds: int,
    new_status: str = "",
) -> dict[str, Any] | None:
    """Atomically append ``event`` to the task's events list, bump version, and
    optionally update status. Returns the updated state dict, or None if the
    task does not exist. Avoids the lost-append problem.

    Falls back to a non-atomic Python implementation when the client does not
    support ``register_script`` (e.g. test fakes).
    """
    if not hasattr(redis_client, "register_script"):
        return _append_event_fallback(redis_client, tasks_key, task_id, event, ttl_seconds, new_status)
    script = _get_append_script(redis_client)
    raw = script(
        keys=[tasks_key],
        args=[encode_redis_json(event), new_status, ttl_seconds],
    )
    if raw is None:
        return None
    return decode_redis_json(raw)


def _append_event_fallback(redis_client, tasks_key, task_id, event, ttl_seconds, new_status):
    """Non-atomic events-append fallback for clients without Lua support."""
    from copy import deepcopy

    cur = redis_client.hget(tasks_key, task_id)
    if cur is None:
        return None
    state = decode_redis_json(cur)
    events = state.setdefault("events", [])
    events.append(deepcopy(event))
    if new_status:
        state["status"] = new_status
    state[VERSION_FIELD] = int(state.get(VERSION_FIELD, 0)) + 1
    redis_client.hset(tasks_key, task_id, encode_redis_json(state))
    redis_client.expire(tasks_key, ttl_seconds)
    return state


def bump_version(state: dict[str, Any]) -> int:
    """Increment and return the ``_version`` field of ``state`` in place."""
    cur = int(state.get(VERSION_FIELD, 0))
    new = cur + 1
    state[VERSION_FIELD] = new
    return new


def get_version(state: dict[str, Any] | None) -> int:
    """Read the ``_version`` field (0 if missing, for backward compat)."""
    if state is None:
        return 0
    return int(state.get(VERSION_FIELD, 0))
