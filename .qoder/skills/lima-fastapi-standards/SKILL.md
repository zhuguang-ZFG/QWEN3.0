---
name: lima-fastapi-standards
description: Python and FastAPI coding standards for the LiMa project. Covers async patterns, error handling, file size limits, import conventions, testing with pytest, ruff linting, and anti-patterns specific to this codebase. Use when writing new Python modules, refactoring code, or reviewing code quality in this repository.
---

# LiMa Python / FastAPI Coding Standards

## File & Function Size

- **File**: target 300 lines max
- **Function**: target 50 lines max
- Exceeding: split into smaller files/functions, not wrap in comments

## Error Handling (Hard Rule)

```python
# FORBIDDEN in production paths:
except Exception:
    pass
except ImportError:
    pass

# REQUIRED instead:
except SomeError as e:
    logger.warning("description of degradation: %s", e)

# If missing critical dep at startup:
if not IMPORTED:
    logger.error("CRITICAL: %s unavailable, feature X disabled", name)
```

## Async Patterns

```python
# FastAPI async endpoint
async def my_endpoint(request: Request):
    result = await some_async_call()
    return JSONResponse(result)

# Wrap sync calls in thread pool when needed
result = await asyncio.to_thread(sync_function, args)

# Streaming response
async def stream():
    async for chunk in data_stream:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"
return StreamingResponse(stream(), media_type="text/event-stream")
```

## Dependency Injection

Modules use `inject_state()` / `inject_deps()` pattern — not global mutable state.

```python
# Good: injected state
_my_state = {}

def inject_state(state: dict):
    global _my_state
    _my_state = state

# Bad: module-level mutable dict that imports depend on
MY_STATE = {}
```

## Import Conventions

```python
# Standard lib first, then third-party, then local
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Request

from routing_engine import route
from backends import get_backend

# PROBLEM: local import inside function shadows module-level name
def handler():
    from chat_request_utils import extract_last_user_text  # SHADOWS!
    # Python treats extract_last_user_text as local for entire function
    # Even code paths that don't reach this line get UnboundLocalError
```

**Rule**: Always import at module level. Never use `from X import Y` inside a function unless the name is used ONLY within that block and nowhere else in the same function.

## Pytest Conventions

```bash
# Config in pytest.ini: asyncio_mode = auto, testpaths = tests, pythonpath = .
# Use project venv for testing (not system Python)
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short
```

```python
# Test file: tests/test_my_module.py
import pytest
from my_module import my_function

class TestMyFunction:
    def test_basic_case(self):
        assert my_function(1) == 2

    def test_edge_case(self):
        assert my_function(0) is None

    @pytest.mark.parametrize("input,expected", [(1, 2), (2, 4)])
    def test_parametrized(self, input, expected):
        assert my_function(input) == expected
```

## Ruff Linting

```bash
ruff check .           # lint
ruff format --check    # format check
ruff format .          # auto-format
```

Config (`ruff.toml`): py310, line-length 120, selected rules `E9, F821, F822, F823, B005, B011, B012, B905, S507`.

## Anti-Patterns in This Codebase

| Pattern | Problem | Fix |
|---------|---------|-----|
| `except Exception: pass` | Silent failure hides bugs | `logger.warning` + exception type |
| Local `from X import Y` | Shadows module-level name | Move import to top of file |
| Giant `server.py` | >500 lines, hard to maintain | Split into focused modules |
| Global mutable state | Race conditions in async | Use DI inject pattern |
| `import *` | Unclear dependencies | Explicit imports |
| Hardcoded API keys | Security risk | Read from `.env` via `os.environ` |
| `time.sleep()` in async | Blocks event loop | Use `asyncio.sleep()` or `asyncio.to_thread()` |

## Naming Conventions

```python
# Modules: snake_case, descriptive
routing_engine.py       # not routingEngine.py
health_tracker.py       # not healthTracker.py

# Classes: PascalCase
class RoutingEngine:
class HealthState:

# Functions: snake_case
def classify_intent():  # not classifyIntent()
def get_backend():      # not getBackend()

# Private functions: leading underscore
def _wrap_tool_stream():  # internal use

# Constants: UPPER_SNAKE_CASE
_TOOLS_BODY_LIMIT = 524288
MAX_RETRIES = 3

# Env vars: LIMA_ prefix
LIMA_API_KEY
LIMA_DEPLOY_KEY_PATH
LIMA_TOOL_BODY_LIMIT
```

## File Organization

Each file should have exactly one responsibility:

```python
# router_http.py          → HTTP routing logic only
# health_tracker.py       → Health state management only
# routing_classifier.py   → Intent classification only
# routing_selector.py     → Backend selection only
```

If a file exceeds 300 lines or does multiple things, split it — don't add sections.

## Logging

```python
import logging
logger = logging.getLogger(__name__)

# Info: normal operation milestones
logger.info("Backend %s selected for request", backend_name)

# Warning: degraded but recoverable
logger.warning("Backend %s health check failed, falling back", name)

# Error: unexpected failure (but never bare except)
logger.error("Request failed: %s", exc_info=True)
```

## Type Hints (Preferred)

```python
def route_request(
    messages: list[dict],
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> dict:
    ...

async def stream_response(
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    ...
```

Pyright is in basic mode — aim for clarity, not 100% coverage.
