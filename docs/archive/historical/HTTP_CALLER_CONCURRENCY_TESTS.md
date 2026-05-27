# HTTP Caller Concurrency Tests (CQ-022/023 follow-up)

Date: 2026-05-25

## Problem

`http_caller.py` migrated to httpx with async helpers, but tests only covered
single-call success/failure paths. Concurrent routing can stress key-pool
selection, health recording, and per-call client lifecycle.

## Decision

Add focused async concurrency tests with mocked httpx clients. No live network
or provider stress harness in this slice.

## Scope

- New tests in `tests/test_http_caller_concurrency.py`:
  - parallel `call_api_async` success
  - parallel mixed success/failure isolation
  - parallel stream async chunk collection
  - threaded sync `call_api` burst (key pool thread safety smoke)

## Out of scope

- Provider-level rate-limit simulation at scale
- Connection-pool reuse / shared client optimization

## Verification

- `pytest tests/test_http_caller_concurrency.py test_http_caller.py -q`
- Full suite green
