# LiMa Dev Search Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give LiMa safe, read-only internet abilities for programming work: search docs, search errors, read URLs, fetch GitHub files, and return source-grounded evidence blocks.

**Architecture:** Build on the existing `search_gateway/`, `tool_gateway/`, and `lima_mcp/` boundaries. Do not wire dev-search tools directly into `routing_engine.py`; expose them through MCP and an explicit Python service so LiMa can call them when a task asks to check docs, inspect an error, or read a URL.

**Tech Stack:** Python standard library, existing `search_gateway.AnySearchAdapter`, existing `search_gateway.tinyfish_transport`, existing MCP-over-HTTP routes in `lima_mcp/server.py`, pytest.

---

## Current Context

LiMa already has the right skeletons:

- `search_gateway/policy.py`: explicit search trigger policy.
- `search_gateway/safety.py`: token/path/private-IP redaction.
- `search_gateway/anysearch_adapter.py`: injected transport wrapper.
- `search_gateway/tinyfish_transport.py`: TinyFish search/fetch implementation with private URL blocking.
- `tool_gateway/registry.py`: tool definitions and intent search.
- `tool_gateway/executor.py`: generic execution boundary.
- `lima_mcp/tools.py`: MCP handlers for repo/memory/retrieval tools.
- `lima_mcp/server.py`: authenticated `/mcp/tools/list` and `/mcp/tools/call`.

The feature should not reuse `tool_dispatcher.py` as-is. That file is a large local prototype with many unrelated public utility tools. This plan extracts only the safe programming-search slice into focused tracked modules.

## Scope

In scope for v0.1:

- Explicit LiMa programming tools only.
- Read-only internet calls.
- Redaction before external search.
- SSRF-safe URL reads.
- Result normalization with URL/title/source/snippet fields.
- MCP exposure for LiMa.
- Unit tests using injected fake transports.

Out of scope for v0.1:

- Shell execution.
- Browser automation.
- VPS operations.
- Automatic code edits based on search results.
- Sending private repository contents to external search.
- Making ordinary `/v1/chat/completions` always search the web.

## External MCP Mapping

The current LiMa-owned tools are the default boundary. External MCP connectors
may improve coverage later, but they should map back to these tool intents
rather than bypassing them:

| External reference | LiMa-owned boundary | Rule |
|---|---|---|
| Context7-style docs lookup | `dev_search_docs` | Prefer versioned official docs. Do not send private source or secrets. |
| Tavily search/extract/map/crawl | `dev_search_docs`, `dev_search_error`, `dev_summarize_sources` | Candidate only after privacy, quota, cache, and citation policy review. |
| Firecrawl extraction | `dev_read_url`, `dev_summarize_sources` | Per-package license review required because Firecrawl license signals vary across server/SDK/runtime packages. |
| Playwright MCP | Browser verification plan, not dev-search v0.1 | Use for long-state UI exploration; prefer CLI/skill checks for simple browser claims to reduce token load. |
| GitHub MCP | `dev_fetch_github_file` and future repo evidence tools | Read first; issue/PR/write actions require approval gates. |

External MCP tools must not make ordinary chat always-search, bypass SSRF
guards, expose API keys to model context, or auto-edit code from fetched
content.

## File Structure

- Create `search_gateway/dev_tools.py`
  - Owns high-level programming search functions.
  - Converts raw adapter results into stable `DevSearchResult` dictionaries.
  - Contains no FastAPI code and no LiMa client code.

- Modify `search_gateway/policy.py`
  - Add dev-search intent detection for programming docs, errors, and explicit URLs.
  - Keep the function pure and deterministic.

- Modify `search_gateway/safety.py`
  - Add `sanitize_error_text()` and `is_public_http_url()`.
  - Reuse existing token/path/private-IP redaction.

- Modify `lima_mcp/__init__.py`
  - Add MCP tool definitions for LiMa dev-search tools.

- Modify `lima_mcp/tools.py`
  - Add handlers that call `search_gateway.dev_tools`.
  - Return deterministic errors when `TINYFISH_API_KEY` is missing.

- Create `tests/test_lima_dev_search_tools.py`
  - Unit-test policy, sanitization, adapter use, URL safety, source formatting, and MCP handler behavior.

- Modify `docs/LIMA_MEMORY.md`
  - Record that LiMa dev-search is explicit, read-only, source-grounded, and not part of default chat routing.

- Modify `STATUS.md`
  - Add a short current-state note after implementation and verification.

## Public Interface

### Python Service Functions

`search_gateway/dev_tools.py` exposes:

```python
from dataclasses import dataclass
from typing import Any, Protocol


class DevSearchAdapter(Protocol):
    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def batch_search(self, queries: list[str], *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def extract_url(self, url: str) -> dict: ...


@dataclass(frozen=True)
class DevSearchResult:
    title: str
    url: str
    snippet: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }


def search_docs(query: str, domains: list[str] | None = None, *, adapter: DevSearchAdapter, max_results: int = 5) -> dict: ...
def search_error(error_text: str, language: str = "", framework: str = "", *, adapter: DevSearchAdapter, max_results: int = 5) -> dict: ...
def read_url(url: str, *, adapter: DevSearchAdapter, max_chars: int = 6000) -> dict: ...
def fetch_github_file(repo: str, path: str, ref: str = "main", *, adapter: DevSearchAdapter, max_chars: int = 8000) -> dict: ...
def summarize_sources(sources: list[dict], *, max_chars: int = 3000) -> dict: ...
```

### MCP Tool Names

- `dev_search_docs`
- `dev_search_error`
- `dev_read_url`
- `dev_fetch_github_file`
- `dev_summarize_sources`

## Task 1: Add Dev-Search Safety Helpers

**Files:**
- Modify: `search_gateway/safety.py`
- Test: `tests/test_lima_dev_search_tools.py`

- [x] **Step 1: Write failing safety tests**

Create `tests/test_lima_dev_search_tools.py` with:

```python
from search_gateway.safety import is_public_http_url, sanitize_error_text


def test_sanitize_error_text_redacts_tokens_paths_and_limits_length():
    secret = "sk-" + "abc123456789xyz"
    raw = f"Traceback token {secret} at D:\\GIT\\.env host 192.168.1.10\n" + ("x" * 6000)

    result = sanitize_error_text(raw, max_chars=200)

    assert "sk-" not in result
    assert "D:\\GIT" not in result
    assert "192.168.1.10" not in result
    assert len(result) <= 200
    assert "[REDACTED_TOKEN]" in result


def test_is_public_http_url_blocks_private_and_non_http_targets():
    assert is_public_http_url("https://docs.python.org/3/library/asyncio.html") is True
    assert is_public_http_url("http://example.com/a") is True
    assert is_public_http_url("file:///etc/passwd") is False
    assert is_public_http_url("http://127.0.0.1:8080/admin") is False
    assert is_public_http_url("http://192.168.1.2/config") is False
    assert is_public_http_url("https://localhost:3000") is False
```

- [x] **Step 2: Run safety tests and verify RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py -q --ignore=active_model
```

Expected: FAIL with `ImportError` for `is_public_http_url` and `sanitize_error_text`.

- [x] **Step 3: Implement safety helpers**

Append these functions to `search_gateway/safety.py`:

```python
import urllib.parse

_PRIVATE_HOST_PREFIXES = (
    "localhost",
    "127.",
    "10.",
    "192.168.",
    "169.254.",
    "0.",
)


def sanitize_error_text(text: str, *, max_chars: int = 2000) -> str:
    redacted = redact_sensitive_query(text or "")
    return redacted[:max_chars]


def is_public_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host.startswith(_PRIVATE_HOST_PREFIXES):
        return False
    if host.startswith("172."):
        parts = host.split(".")
        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return False
    return True
```

- [x] **Step 4: Run safety tests and verify GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py -q --ignore=active_model
```

Expected: `2 passed`.

## Task 2: Add Dev-Search Policy

**Files:**
- Modify: `search_gateway/policy.py`
- Modify test: `tests/test_lima_dev_search_tools.py`

- [x] **Step 1: Add failing policy tests**

Append:

```python
from search_gateway.policy import should_dev_search


def test_should_dev_search_detects_programming_docs_errors_and_urls():
    assert should_dev_search("查一下 FastAPI 官方文档 Depends 怎么用") is True
    assert should_dev_search("search latest React useActionState docs") is True
    assert should_dev_search("read https://docs.python.org/3/library/asyncio.html") is True
    assert should_dev_search("这个 TypeError: object NoneType cannot be awaited 怎么修") is True
    assert should_dev_search("帮我重构 routing_engine.py 的命名") is False
```

- [x] **Step 2: Run policy test and verify RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py::test_should_dev_search_detects_programming_docs_errors_and_urls -q --ignore=active_model
```

Expected: FAIL with `ImportError` for `should_dev_search`.

- [x] **Step 3: Implement policy**

Append to `search_gateway/policy.py`:

```python
DEV_SEARCH_MARKERS = (
    "docs",
    "documentation",
    "official doc",
    "search latest",
    "read http://",
    "read https://",
    "error",
    "exception",
    "traceback",
    "typeerror",
    "valueerror",
    "runtimeerror",
    "importerror",
    "怎么修",
    "官方文档",
    "查一下",
    "报错",
    "异常",
)


def should_dev_search(query: str) -> bool:
    lowered = (query or "").lower()
    return any(marker in lowered for marker in DEV_SEARCH_MARKERS)
```

- [x] **Step 4: Run policy tests and verify GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py -q --ignore=active_model
```

Expected: `3 passed`.

## Task 3: Implement `search_gateway.dev_tools`

**Files:**
- Create: `search_gateway/dev_tools.py`
- Modify test: `tests/test_lima_dev_search_tools.py`

- [x] **Step 1: Add failing service tests**

Append:

```python
from search_gateway.dev_tools import (
    fetch_github_file,
    read_url,
    search_docs,
    search_error,
    summarize_sources,
)


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def search(self, query, *, domain=None, max_results=5):
        self.calls.append(("search", query, domain, max_results))
        return {
            "ok": True,
            "results": [
                {
                    "title": "FastAPI Depends",
                    "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
                    "snippet": "Dependency injection docs",
                }
            ],
        }

    def batch_search(self, queries, *, domain=None, max_results=5):
        self.calls.append(("batch_search", queries, domain, max_results))
        return {"ok": True, "results": []}

    def extract_url(self, url):
        self.calls.append(("extract_url", url))
        return {"ok": True, "text": "hello docs body", "title": "Docs"}


def test_search_docs_normalizes_results_and_domains():
    adapter = FakeAdapter()

    result = search_docs("FastAPI Depends", ["fastapi.tiangolo.com"], adapter=adapter, max_results=3)

    assert result["ok"] is True
    assert result["tool"] == "dev_search_docs"
    assert result["results"][0]["url"].startswith("https://fastapi")
    assert adapter.calls[0] == ("search", "FastAPI Depends", "fastapi.tiangolo.com", 3)


def test_search_error_sanitizes_stack_before_search():
    adapter = FakeAdapter()
    secret = "sk-" + "abc123456789xyz"

    result = search_error(f"TypeError boom {secret} D:\\GIT\\.env", language="python", adapter=adapter)

    assert result["ok"] is True
    assert "sk-" not in adapter.calls[0][1]
    assert "D:\\GIT" not in adapter.calls[0][1]
    assert "python" in adapter.calls[0][1]


def test_read_url_blocks_private_targets():
    adapter = FakeAdapter()

    result = read_url("http://127.0.0.1:8080/admin", adapter=adapter)

    assert result == {"ok": False, "tool": "dev_read_url", "error": "url_blocked"}
    assert adapter.calls == []


def test_fetch_github_file_uses_raw_github_url():
    adapter = FakeAdapter()

    result = fetch_github_file("psf/requests", "src/requests/sessions.py", "main", adapter=adapter)

    assert result["ok"] is True
    assert adapter.calls[0] == (
        "extract_url",
        "https://raw.githubusercontent.com/psf/requests/main/src/requests/sessions.py",
    )


def test_summarize_sources_builds_compact_evidence_block():
    result = summarize_sources([
        {"title": "A", "url": "https://example.com/a", "snippet": "alpha"},
        {"title": "B", "url": "https://example.com/b", "snippet": "beta"},
    ], max_chars=500)

    assert result["ok"] is True
    assert "https://example.com/a" in result["evidence"]
    assert "alpha" in result["evidence"]
```

- [x] **Step 2: Run service tests and verify RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py -q --ignore=active_model
```

Expected: FAIL because `search_gateway.dev_tools` does not exist.

- [x] **Step 3: Create `search_gateway/dev_tools.py`**

Create the file with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import urllib.parse

from .safety import is_public_http_url, sanitize_error_text


class DevSearchAdapter(Protocol):
    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def batch_search(self, queries: list[str], *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def extract_url(self, url: str) -> dict: ...


@dataclass(frozen=True)
class DevSearchResult:
    title: str
    url: str
    snippet: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }


def _normalize_results(raw: dict, *, source: str) -> list[dict[str, str]]:
    results = raw.get("results", []) if isinstance(raw, dict) else []
    normalized: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "Untitled")[:200]
        url = str(item.get("url") or item.get("link") or "")
        snippet = str(item.get("snippet") or item.get("content") or item.get("text") or "")[:1000]
        normalized.append(DevSearchResult(title, url, snippet, source).as_dict())
    return normalized


def search_docs(
    query: str,
    domains: list[str] | None = None,
    *,
    adapter: DevSearchAdapter,
    max_results: int = 5,
) -> dict:
    clean_query = sanitize_error_text(query, max_chars=500)
    domain = domains[0] if domains else None
    raw = adapter.search(clean_query, domain=domain, max_results=max_results)
    if not raw.get("ok"):
        return {"ok": False, "tool": "dev_search_docs", "error": raw.get("error", "search_failed")}
    return {"ok": True, "tool": "dev_search_docs", "results": _normalize_results(raw, source="search")}


def search_error(
    error_text: str,
    language: str = "",
    framework: str = "",
    *,
    adapter: DevSearchAdapter,
    max_results: int = 5,
) -> dict:
    parts = [sanitize_error_text(error_text, max_chars=1500)]
    if language:
        parts.append(language)
    if framework:
        parts.append(framework)
    query = " ".join(part for part in parts if part).strip()
    raw = adapter.search(query, domain=None, max_results=max_results)
    if not raw.get("ok"):
        return {"ok": False, "tool": "dev_search_error", "error": raw.get("error", "search_failed")}
    return {"ok": True, "tool": "dev_search_error", "results": _normalize_results(raw, source="error_search")}


def read_url(url: str, *, adapter: DevSearchAdapter, max_chars: int = 6000) -> dict:
    if not is_public_http_url(url):
        return {"ok": False, "tool": "dev_read_url", "error": "url_blocked"}
    raw = adapter.extract_url(url)
    if not raw.get("ok"):
        return {"ok": False, "tool": "dev_read_url", "error": raw.get("error", "fetch_failed")}
    return {
        "ok": True,
        "tool": "dev_read_url",
        "url": url,
        "title": str(raw.get("title") or "")[:200],
        "text": str(raw.get("text") or "")[:max_chars],
    }


def fetch_github_file(
    repo: str,
    path: str,
    ref: str = "main",
    *,
    adapter: DevSearchAdapter,
    max_chars: int = 8000,
) -> dict:
    safe_repo = repo.strip().strip("/")
    safe_path = path.strip().lstrip("/")
    safe_ref = urllib.parse.quote(ref.strip() or "main", safe="")
    if safe_repo.count("/") != 1 or not safe_path:
        return {"ok": False, "tool": "dev_fetch_github_file", "error": "invalid_github_target"}
    raw_url = f"https://raw.githubusercontent.com/{safe_repo}/{safe_ref}/{safe_path}"
    read = read_url(raw_url, adapter=adapter, max_chars=max_chars)
    read["tool"] = "dev_fetch_github_file"
    read["repo"] = safe_repo
    read["path"] = safe_path
    read["ref"] = ref
    return read


def summarize_sources(sources: list[dict], *, max_chars: int = 3000) -> dict:
    lines: list[str] = []
    for idx, source in enumerate(sources, start=1):
        title = str(source.get("title") or "Untitled")[:160]
        url = str(source.get("url") or "")[:300]
        snippet = str(source.get("snippet") or source.get("text") or "")[:700]
        lines.append(f"[{idx}] {title}\nURL: {url}\nEvidence: {snippet}")
    evidence = "\n\n".join(lines)[:max_chars]
    return {"ok": True, "tool": "dev_summarize_sources", "evidence": evidence}
```

- [x] **Step 4: Run service tests and verify GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py -q --ignore=active_model
```

Expected: all tests in this file pass.

## Task 4: Expose Dev-Search Through MCP

**Files:**
- Modify: `lima_mcp/__init__.py`
- Modify: `lima_mcp/tools.py`
- Modify test: `tests/test_lima_dev_search_tools.py`

- [x] **Step 1: Add failing MCP tests**

Append:

```python
from lima_mcp import TOOL_DEFINITIONS
from lima_mcp.tools import handle_tool_call


def test_mcp_lists_dev_search_tools():
    names = {tool["name"] for tool in TOOL_DEFINITIONS}

    assert "dev_search_docs" in names
    assert "dev_search_error" in names
    assert "dev_read_url" in names
    assert "dev_fetch_github_file" in names
    assert "dev_summarize_sources" in names


def test_mcp_dev_read_url_blocks_private_url_without_network():
    result = handle_tool_call("dev_read_url", {"url": "http://127.0.0.1:8080/admin"})

    assert result["ok"] is False
    assert result["error"] == "url_blocked"
```

- [x] **Step 2: Run MCP tests and verify RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py::test_mcp_lists_dev_search_tools tests\test_lima_dev_search_tools.py::test_mcp_dev_read_url_blocks_private_url_without_network -q --ignore=active_model
```

Expected: FAIL because tool definitions and handlers do not include dev-search tools.

- [x] **Step 3: Add MCP tool definitions**

Append these entries to `TOOL_DEFINITIONS` in `lima_mcp/__init__.py`:

```python
{
    "name": "dev_search_docs",
    "description": "Search public programming documentation and return source-grounded results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "domains": {"type": "array", "items": {"type": "string"}},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    },
},
{
    "name": "dev_search_error",
    "description": "Search public sources for a sanitized programming error or stack trace.",
    "input_schema": {
        "type": "object",
        "properties": {
            "error_text": {"type": "string"},
            "language": {"type": "string"},
            "framework": {"type": "string"},
            "max_results": {"type": "integer"},
        },
        "required": ["error_text"],
    },
},
{
    "name": "dev_read_url",
    "description": "Read a public HTTP(S) URL and return extracted text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer"},
        },
        "required": ["url"],
    },
},
{
    "name": "dev_fetch_github_file",
    "description": "Fetch a public GitHub file through raw.githubusercontent.com.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {"type": "string"},
            "path": {"type": "string"},
            "ref": {"type": "string"},
            "max_chars": {"type": "integer"},
        },
        "required": ["repo", "path"],
    },
},
{
    "name": "dev_summarize_sources",
    "description": "Turn source dictionaries into a compact evidence block for LiMa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sources": {"type": "array", "items": {"type": "object"}},
            "max_chars": {"type": "integer"},
        },
        "required": ["sources"],
    },
},
```

- [x] **Step 4: Add MCP handlers**

Modify `lima_mcp/tools.py`:

```python
def handle_tool_call(name: str, arguments: dict) -> dict:
    handlers = {
        "search_repo": _search_repo,
        "search_memory": _search_memory,
        "get_retrieval_trace": _get_retrieval_trace,
        "dev_search_docs": _dev_search_docs,
        "dev_search_error": _dev_search_error,
        "dev_read_url": _dev_read_url,
        "dev_fetch_github_file": _dev_fetch_github_file,
        "dev_summarize_sources": _dev_summarize_sources,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(arguments)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _dev_adapter():
    from search_gateway.anysearch_adapter import AnySearchAdapter
    from search_gateway.tinyfish_transport import tinyfish_transport

    return AnySearchAdapter(tinyfish_transport)


def _dev_search_docs(args: dict) -> dict:
    from search_gateway.dev_tools import search_docs

    return search_docs(
        args.get("query", ""),
        args.get("domains") or None,
        adapter=_dev_adapter(),
        max_results=int(args.get("max_results", 5)),
    )


def _dev_search_error(args: dict) -> dict:
    from search_gateway.dev_tools import search_error

    return search_error(
        args.get("error_text", ""),
        language=args.get("language", ""),
        framework=args.get("framework", ""),
        adapter=_dev_adapter(),
        max_results=int(args.get("max_results", 5)),
    )


def _dev_read_url(args: dict) -> dict:
    from search_gateway.dev_tools import read_url

    return read_url(
        args.get("url", ""),
        adapter=_dev_adapter(),
        max_chars=int(args.get("max_chars", 6000)),
    )


def _dev_fetch_github_file(args: dict) -> dict:
    from search_gateway.dev_tools import fetch_github_file

    return fetch_github_file(
        args.get("repo", ""),
        args.get("path", ""),
        args.get("ref", "main"),
        adapter=_dev_adapter(),
        max_chars=int(args.get("max_chars", 8000)),
    )


def _dev_summarize_sources(args: dict) -> dict:
    from search_gateway.dev_tools import summarize_sources

    return summarize_sources(
        args.get("sources", []),
        max_chars=int(args.get("max_chars", 3000)),
    )
```

- [x] **Step 5: Run MCP tests and verify GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py tests\test_mcp_tools.py -q --ignore=active_model
```

Expected: all selected tests pass.

## Task 5: Add Evidence Formatting Contract for LiMa

**Files:**
- Modify: `search_gateway/dev_tools.py`
- Modify test: `tests/test_lima_dev_search_tools.py`

- [x] **Step 1: Add failing evidence contract test**

Append:

```python
from search_gateway.dev_tools import build_prompt_evidence


def test_build_prompt_evidence_includes_source_urls_and_tool_names():
    evidence = build_prompt_evidence([
        {
            "tool": "dev_search_docs",
            "results": [
                {
                    "title": "Python asyncio",
                    "url": "https://docs.python.org/3/library/asyncio.html",
                    "snippet": "asyncio runs coroutines",
                    "source": "search",
                }
            ],
        }
    ], max_chars=1000)

    assert evidence["ok"] is True
    assert "dev_search_docs" in evidence["evidence"]
    assert "https://docs.python.org" in evidence["evidence"]
    assert "asyncio runs coroutines" in evidence["evidence"]
```

- [x] **Step 2: Run evidence test and verify RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py::test_build_prompt_evidence_includes_source_urls_and_tool_names -q --ignore=active_model
```

Expected: FAIL because `build_prompt_evidence` does not exist.

- [x] **Step 3: Implement `build_prompt_evidence`**

Append to `search_gateway/dev_tools.py`:

```python
def build_prompt_evidence(tool_outputs: list[dict], *, max_chars: int = 4000) -> dict:
    sections: list[str] = []
    for output in tool_outputs:
        tool_name = str(output.get("tool") or "unknown_tool")
        if output.get("results"):
            for result in output["results"]:
                sections.append(
                    f"Tool: {tool_name}\n"
                    f"Title: {str(result.get('title', 'Untitled'))[:160]}\n"
                    f"URL: {str(result.get('url', ''))[:300]}\n"
                    f"Evidence: {str(result.get('snippet', ''))[:700]}"
                )
        elif output.get("text"):
            sections.append(
                f"Tool: {tool_name}\n"
                f"URL: {str(output.get('url', ''))[:300]}\n"
                f"Evidence: {str(output.get('text', ''))[:900]}"
            )
    return {"ok": True, "tool": "dev_prompt_evidence", "evidence": "\n\n".join(sections)[:max_chars]}
```

- [x] **Step 4: Run evidence tests and verify GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py -q --ignore=active_model
```

Expected: all tests in this file pass.

## Task 6: Register Dev-Search Tools in Tool Registry

**Files:**
- Modify: `tool_gateway/registry.py`
- Modify test: `tests/test_tool_gateway.py`

- [x] **Step 1: Add failing registry factory test**

Append to `tests/test_tool_gateway.py`:

```python
from tool_gateway.registry import build_default_registry


def test_default_registry_includes_lima_dev_search_tools():
    registry = build_default_registry()

    matches = registry.search("programming docs error url")
    names = {tool.name for tool in matches}

    assert "dev_search_docs" in names
    assert "dev_search_error" in names
    assert "dev_read_url" in names
```

- [x] **Step 2: Run registry test and verify RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_tool_gateway.py::test_default_registry_includes_lima_dev_search_tools -q --ignore=active_model
```

Expected: FAIL because `build_default_registry` does not exist.

- [x] **Step 3: Implement default registry factory**

Append to `tool_gateway/registry.py`:

```python
def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="dev_search_docs",
        description="Search public programming documentation for LiMa.",
        tags=("programming", "docs", "search", "readonly", "lima"),
    ))
    registry.register(ToolDefinition(
        name="dev_search_error",
        description="Search public sources for sanitized programming errors.",
        tags=("programming", "error", "traceback", "debug", "readonly", "lima"),
    ))
    registry.register(ToolDefinition(
        name="dev_read_url",
        description="Read a public HTTP or HTTPS URL for LiMa.",
        tags=("url", "docs", "fetch", "readonly", "lima"),
    ))
    registry.register(ToolDefinition(
        name="dev_fetch_github_file",
        description="Fetch a public GitHub file for reference.",
        tags=("github", "source", "reference", "readonly", "lima"),
    ))
    registry.register(ToolDefinition(
        name="dev_summarize_sources",
        description="Summarize source dictionaries into prompt evidence.",
        tags=("evidence", "summary", "sources", "lima"),
    ))
    return registry
```

- [x] **Step 4: Run registry tests and verify GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_tool_gateway.py -q --ignore=active_model
```

Expected: all `test_tool_gateway.py` tests pass.

## Task 7: Documentation Update

**Files:**
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `STATUS.md`

- [x] **Step 1: Update long-term memory**

Add a dated entry to `docs/LIMA_MEMORY.md`:

```markdown
### 2026-05-23 - LiMa Dev Search Tools v0.1

- LiMa dev-search tools are explicit, read-only, and MCP-exposed.
- Tools added: `dev_search_docs`, `dev_search_error`, `dev_read_url`, `dev_fetch_github_file`, `dev_summarize_sources`.
- External search input is redacted before transport: API-token patterns, Windows paths, and private IPs are removed.
- URL reads reject non-HTTP schemes and private/loopback targets.
- These tools are not part of default chat routing and must not send private repository contents to external search.
```

- [x] **Step 2: Update status**

Add a short line to `STATUS.md` under the current capability section:

```markdown
- LiMa has planned read-only dev-search tools through MCP: docs search, error search, public URL read, public GitHub file fetch, and source evidence summarization.
```

- [x] **Step 3: Verify docs mention the new tools**

Run:

```powershell
rg -n "LiMa Dev Search Tools|dev_search_docs|dev_search_error|dev_read_url|dev_fetch_github_file" docs\LIMA_MEMORY.md STATUS.md
```

Expected: output includes both `docs/LIMA_MEMORY.md` and `STATUS.md`.

## Task 8: Final Verification

**Files:**
- No new files.

- [x] **Step 1: Compile touched Python modules**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m compileall -q search_gateway tool_gateway lima_mcp tests
```

Expected: exit code `0`.

- [x] **Step 2: Run focused tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_lima_dev_search_tools.py tests\test_search_gateway.py tests\test_tool_gateway.py tests\test_mcp_tools.py -q --ignore=active_model
```

Expected: all selected tests pass.

- [x] **Step 3: Run full suite and record current unrelated failures**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q --ignore=active_model
```

Expected before fixing existing prompt tests: full suite may still show the known 5 prompt-engineering failures from chat role text changes. Do not claim the whole repo is green unless this command reports `0 failed`.

- [x] **Step 4: Secret scan for touched areas**

Run:

```powershell
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" search_gateway tool_gateway lima_mcp tests docs\LIMA_MEMORY.md STATUS.md
```

Expected: no real secrets. Test fixture strings such as `"sk-" + "abc123456789xyz"` are acceptable when split or clearly fake.

- [x] **Step 5: Review Git status**

Run:

```powershell
git status --short -- search_gateway tool_gateway lima_mcp tests docs\LIMA_MEMORY.md STATUS.md docs\superpowers\plans\2026-05-23-lima-dev-search-tools.md
```

Expected: only intended files appear.

## Risk Controls

- **Privacy:** never send raw private repo files, `.env`, local paths, or tokens to search. `sanitize_error_text()` and `redact_sensitive_query()` run before search.
- **SSRF:** `is_public_http_url()` blocks loopback, private IP ranges, non-HTTP schemes, and empty hosts before any fetch.
- **Blast radius:** dev-search tools are MCP-only in v0.1. They do not change default OpenAI-compatible chat routing.
- **Reproducibility:** all new runtime modules must be tracked by Git. Do not depend on untracked `tool_dispatcher.py`.
- **Operational failure:** missing `TINYFISH_API_KEY` returns structured tool errors and must not break LiMa Server startup.
- **Evidence quality:** every useful result must include URL/source/title/snippet or extracted URL/text so LiMa can cite sources in its reasoning.

## Implementation Order

1. Safety helpers.
2. Dev-search intent policy.
3. Dev-search service functions.
4. MCP tool definitions and handlers.
5. Prompt evidence formatter.
6. Tool registry entries.
7. Docs and status.
8. Compile, focused tests, full tests, secret scan.

## Self-Review

- Spec coverage: the plan covers docs search, error search, URL read, GitHub file fetch, source summarization, MCP exposure, redaction, SSRF blocking, and tests.
- Placeholder scan: no step relies on an undefined placeholder; each code task includes concrete function names and expected commands.
- Type consistency: `DevSearchAdapter`, `DevSearchResult`, MCP tool names, and test names are consistent across tasks.
- Scope check: the plan stays inside read-only LiMa dev-search and does not include shell tools, browser tools, VPS control, or default chat auto-search.
