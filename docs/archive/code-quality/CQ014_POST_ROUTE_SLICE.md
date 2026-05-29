# CQ-014 Slice: Post-Route Integration Extraction

Date: 2026-05-25

## Problem

`routing_engine.py` exceeded the 300-line target and mixed routing decisions with
post-route side effects (narrative handoff, hierarchical memory, response pipeline,
observability). Silent `except ...: pass` blocks hid production failures.

## Decision

Extract post-route integrations into `route_post_process.py` and replace broad
silent catches with `logger.warning(..., exc_info=True)` for unexpected errors.
`ImportError` remains quiet when optional modules are absent.

## Scope (this slice)

- New module: `route_post_process.py`
- `routing_engine.route()` delegates post-route work to `apply_post_route_integrations()`
- `http_caller.py` prefix-cache optimization logs unexpected failures

## Out of scope (follow-up slices)

- `smart_router.py`, `server.py`, `routes/admin.py`, `http_caller.py` full split
- Making `build_default_pipeline()` the production authority (see `REQUEST_PIPELINE_AUTHORITY.md`)

## Verification

- `pytest tests/test_route_post_process.py test_routing_engine.py -q`
- Full suite green before VPS deploy
