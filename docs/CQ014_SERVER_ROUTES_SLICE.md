# CQ-014 Slice 3: Server Route Registration Extraction

Date: 2026-05-25

## Problem

`server.py` mixed chat orchestration with ~100 lines of router registration,
inject_state wiring, and optional module loading. This made the entry file hard
to navigate and kept it above the 300-line target.

## Decision

Extract all `app.include_router(...)` and related inject_state calls into
`routes/route_registry.py` with a single `register_all_routes(app, deps)` entry.

`server.py` keeps app creation, middleware, stats, and chat handlers; it calls
the registry once and re-exports handler aliases for backward compatibility.

## Scope (this slice)

- New module: `routes/route_registry.py`
- `server.py` delegates router mounting to registry
- Test: `tests/test_route_registry.py`

## Out of scope

- Extracting `_handle_chat` / streaming logic from `server.py`
- Splitting `smart_router.py` or `http_caller.py` implementation files

## Verification

- `pytest tests/test_route_registry.py tests/test_chat_endpoints.py tests/test_system_endpoints.py -q`
- Full suite green before VPS deploy
