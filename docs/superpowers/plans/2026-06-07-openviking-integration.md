# OpenViking Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate OpenViking as a context enrichment layer for LiMa, adding a pipeline processor for knowledge retrieval and L0/L1/L2 tiered skill loading to reduce token consumption.

**Architecture:** OpenViking runs as an HTTP server (port 1933) alongside LiMa. A thin async client (`openviking_client.py`) wraps the REST API. A new pipeline processor (`openviking_context_processor`) queries OpenViking after cache optimization and injects retrieved context into `ctx.code_context`. Separately, the skills injector gains L0/L1/L2 tiered loading: each skill file gets auto-generated `.abstract` and `.overview` sidecar files, and the injector selects the appropriate tier based on token budget.

**Tech Stack:** Python 3.10+, OpenViking (pip), httpx (async HTTP), pytest, existing LiMa test infrastructure.

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `openviking_client.py` | Thin sync/async wrapper for OpenViking HTTP API |
| Create | `context_pipeline/openviking_processor.py` | Stage 6 processor: query OpenViking, inject context |
| Modify | `context_pipeline/__init__.py` | Add `openviking_context: str` field to `RequestContext` |
| Modify | `context_pipeline/factory.py` | Register Stage 6 in `build_default_pipeline()` |
| Modify | `skills_injector.py` | Add L0/L1/L2 tiered loading logic |
| Create | `skills_tier_builder.py` | CLI utility to generate `.abstract` / `.overview` sidecars |
| Create | `tests/test_openviking_client.py` | Unit tests for client wrapper |
| Create | `tests/test_openviking_processor.py` | Unit tests for pipeline processor |
| Create | `tests/test_skills_tiered.py` | Unit tests for tiered skill loading |
| Modify | `tests/test_context_pipeline.py` | Update stage count assertions (5 → 6) |
| Create | `data/ov.conf` | OpenViking server configuration |

---

### Task 1: Install OpenViking and Configure Server

**Files:**
- Create: `D:\QWEN3.0\data\ov.conf`

- [ ] **Step 1: Install OpenViking Python package**

Run:
```bash
pip install openviking --upgrade
```
Expected: `Successfully installed openviking-X.Y.Z`

- [ ] **Step 2: Create OpenViking server config**

Create `D:\QWEN3.0\data\ov.conf`:
```json
{
  "storage": {
    "workspace": "D:/QWEN3.0/data/openviking_workspace"
  },
  "log": {
    "level": "INFO",
    "output": "stdout"
  },
  "embedding": {
    "dense": {
      "api_base": "https://api.openai.com/v1",
      "api_key": "<REPLACE_WITH_OPENAI_KEY>",
      "provider": "openai",
      "dimension": 3072,
      "model": "text-embedding-3-large"
    },
    "max_concurrent": 10,
    "text_source": "content_only",
    "max_input_tokens": 4096
  },
  "vlm": {
    "api_base": "https://new.sharedchat.cc/codex",
    "provider": "openai-codex",
    "model": "gpt-5.3-codex",
    "max_concurrent": 8
  }
}
```

- [ ] **Step 3: Validate OpenViking setup**

Run:
```bash
set OPENVIKING_CONFIG_FILE=D:\QWEN3.0\data\ov.conf
openviking-server doctor
```
Expected: All checks pass (config, Python version, embedding connectivity).

- [ ] **Step 4: Commit config template**

```bash
git add data/ov.conf
git commit -m "chore: add OpenViking server config template"
```

---

### Task 2: Build OpenViking HTTP Client Wrapper

**Files:**
- Create: `D:\QWEN3.0\openviking_client.py`
- Test: `D:\QWEN3.0\tests\test_openviking_client.py`

- [ ] **Step 1: Write the failing test for client init**

Create `D:\QWEN3.0\tests\test_openviking_client.py`:
```python
"""Tests for OpenViking HTTP client wrapper."""
import pytest
from unittest.mock import patch, MagicMock


def test_client_default_url():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient()
    assert client.base_url == "http://localhost:1933"


def test_client_custom_url():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient(base_url="http://10.0.0.1:1933")
    assert client.base_url == "http://10.0.0.1:1933"


def test_client_is_available_true():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient()
    with patch.object(client, '_get', return_value={"status": "ok"}):
        assert client.is_available() is True


def test_client_is_available_false_on_connection_error():
    from openviking_client import OpenVikingClient
    client = OpenVikingClient()
    with patch.object(client, '_get', side_effect=ConnectionError("refused")):
        assert client.is_available() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_openviking_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openviking_client'`

- [ ] **Step 3: Write minimal OpenVikingClient implementation**

Create `D:\QWEN3.0\openviking_client.py`:
```python
"""Thin sync wrapper for OpenViking HTTP API (localhost:1933).

OpenViking is an optional dependency. If the server is unreachable,
all methods return safe defaults (empty strings, False).

Environment:
    OPENVIKING_URL: Override default http://localhost:1933
    LIMA_OPENVIKING_ENABLED: Set to "1" to enable (default: "0")
"""
import logging
import os
from urllib.request import urlopen, Request
from urllib.error import URLError

import json

_log = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:1933"
_TIMEOUT = 5  # seconds — context retrieval must be fast


class OpenVikingClient:
    """Sync HTTP client for OpenViking server."""

    def __init__(self, base_url: str = "", timeout: int = _TIMEOUT) -> None:
        self.base_url = (
            base_url
            or os.environ.get("OPENVIKING_URL", "")
            or _DEFAULT_URL
        ).rstrip("/")
        self._timeout = timeout

    def is_available(self) -> bool:
        """Check if OpenViking server is reachable."""
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    def find(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search across all Viking resources.

        Returns list of {"uri": str, "content": str, "score": float}.
        Returns empty list on any error.
        """
        try:
            data = self._post("/api/v1/find", {"query": query, "top_k": top_k})
            return data.get("results", [])
        except Exception as exc:
            _log.debug("openviking find failed: %s", exc)
            return []

    def read(self, uri: str, layer: str = "L1") -> str:
        """Read a specific Viking URI at the given layer (L0/L1/L2).

        Returns the text content, or empty string on error.
        """
        try:
            data = self._post("/api/v1/read", {"uri": uri, "layer": layer})
            return data.get("content", "")
        except Exception as exc:
            _log.debug("openviking read failed: %s", exc)
            return ""

    def format_context(self, results: list[dict], max_chars: int = 1500) -> str:
        """Format retrieval results into injectable context text."""
        if not results:
            return ""
        lines = ["[OpenViking Context]"]
        total = 0
        for r in results:
            uri = r.get("uri", "unknown")
            content = r.get("content", "")
            entry = f"- {uri}: {content[:200]}"
            if total + len(entry) > max_chars:
                break
            lines.append(entry)
            total += len(entry)
        return "\n".join(lines)

    # ── Internal HTTP helpers ──────────────────────────────────────────

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = Request(url, method="GET")
        with urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="POST", headers={
            "Content-Type": "application/json",
        })
        with urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())


# ── Singleton accessor ────────────────────────────────────────────────────

_client: OpenVikingClient | None = None


def get_openviking_client() -> OpenVikingClient | None:
    """Return singleton client if enabled, else None.

    Controlled by LIMA_OPENVIKING_ENABLED env var (default "0").
    """
    global _client
    if os.environ.get("LIMA_OPENVIKING_ENABLED", "0") != "1":
        return None
    if _client is None:
        _client = OpenVikingClient()
    return _client
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_openviking_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add openviking_client.py tests/test_openviking_client.py
git commit -m "feat: add OpenViking HTTP client wrapper"
```

---

### Task 3: Add `openviking_context` Field to RequestContext

**Files:**
- Modify: `D:\QWEN3.0\context_pipeline\__init__.py`

- [ ] **Step 1: Write test for new field**

Append to `D:\QWEN3.0\tests\test_context_pipeline.py`:
```python
def test_request_context_has_openviking_field():
    from context_pipeline import RequestContext
    ctx = RequestContext()
    assert hasattr(ctx, "openviking_context")
    assert ctx.openviking_context == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_context_pipeline.py::test_request_context_has_openviking_field -v`
Expected: FAIL with `AttributeError`

- [ ] **Step 3: Add field to RequestContext dataclass**

In `D:\QWEN3.0\context_pipeline\__init__.py`, add after `recalled_memory_ids`:
```python
    openviking_context: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_context_pipeline.py::test_request_context_has_openviking_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add context_pipeline/__init__.py tests/test_context_pipeline.py
git commit -m "feat: add openviking_context field to RequestContext"
```

---

### Task 4: Create OpenViking Pipeline Processor

**Files:**
- Create: `D:\QWEN3.0\context_pipeline\openviking_processor.py`
- Test: `D:\QWEN3.0\tests\test_openviking_processor.py`

- [ ] **Step 1: Write failing test for processor**

Create `D:\QWEN3.0\tests\test_openviking_processor.py`:
```python
"""Tests for the OpenViking context pipeline processor (Stage 6)."""
import pytest
from unittest.mock import patch, MagicMock
from context_pipeline import RequestContext


def test_processor_skips_when_client_none():
    """If OpenViking is disabled, processor is a no-op."""
    from context_pipeline.openviking_processor import openviking_context_processor
    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "fix the bug"}],
        system_prompt="existing prompt",
    )
    with patch("context_pipeline.openviking_processor.get_openviking_client", return_value=None):
        result = openviking_context_processor(ctx)
    assert result.openviking_context == ""
    assert result.system_prompt == "existing prompt"


def test_processor_skips_non_coding_scenarios():
    """Only coding scenarios get OpenViking enrichment."""
    from context_pipeline.openviking_processor import openviking_context_processor
    ctx = RequestContext(scenario="chat", system_prompt="chat prompt")
    with patch("context_pipeline.openviking_processor.get_openviking_client") as mock_get:
        result = openviking_context_processor(ctx)
    assert result.openviking_context == ""
    mock_get.assert_not_called()


def test_processor_injects_context_into_system_prompt():
    """When OpenViking returns results, they appear in system_prompt."""
    from context_pipeline.openviking_processor import openviking_context_processor

    mock_client = MagicMock()
    mock_client.find.return_value = [
        {"uri": "viking://resources/api_docs", "content": "Use /v1/models endpoint", "score": 0.92},
    ]
    mock_client.format_context.return_value = "[OpenViking Context]\n- viking://resources/api_docs: Use /v1/models endpoint"

    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "how to list models?"}],
        system_prompt="You are LiMa.",
    )
    with patch("context_pipeline.openviking_processor.get_openviking_client", return_value=mock_client):
        result = openviking_context_processor(ctx)

    assert "OpenViking Context" in result.system_prompt
    assert result.openviking_context != ""


def test_processor_handles_empty_results():
    """If OpenViking returns no results, system_prompt is unchanged."""
    from context_pipeline.openviking_processor import openviking_context_processor

    mock_client = MagicMock()
    mock_client.find.return_value = []
    mock_client.format_context.return_value = ""

    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="original prompt",
    )
    with patch("context_pipeline.openviking_processor.get_openviking_client", return_value=mock_client):
        result = openviking_context_processor(ctx)

    assert result.system_prompt == "original prompt"
    assert result.openviking_context == ""


def test_processor_extracts_query_from_last_user_message():
    """The search query should be the last user message content."""
    from context_pipeline.openviking_processor import _extract_query

    messages = [
        {"role": "system", "content": "You are LiMa"},
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "how to fix the routing bug in server.py?"},
    ]
    query = _extract_query(messages)
    assert "routing bug" in query
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_openviking_processor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'context_pipeline.openviking_processor'`

- [ ] **Step 3: Implement the processor**

Create `D:\QWEN3.0\context_pipeline\openviking_processor.py`:
```python
"""Stage 6: OpenViking context enrichment processor.

Queries the OpenViking server for relevant resources based on the
last user message, and injects results into the system prompt.

Gated by LIMA_OPENVIKING_ENABLED=1 env var.
"""
from __future__ import annotations

import logging

from . import RequestContext

_log = logging.getLogger(__name__)


def _extract_query(messages: list[dict]) -> str:
    """Extract search query from the last user message."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:500]
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part["text"][:500]
    return ""


def openviking_context_processor(ctx: RequestContext) -> RequestContext:
    """Stage 6: Enrich context with OpenViking knowledge retrieval.

    Only activates for coding scenarios when LIMA_OPENVIKING_ENABLED=1.
    Queries OpenViking with the last user message, injects top-k results
    into the system prompt as an [OpenViking Context] block.
    """
    if ctx.scenario != "coding":
        return ctx

    from openviking_client import get_openviking_client

    client = get_openviking_client()
    if client is None:
        return ctx

    query = _extract_query(ctx.messages)
    if not query:
        return ctx

    results = client.find(query, top_k=5)
    context_text = client.format_context(results, max_chars=1500)

    if not context_text:
        return ctx

    ctx.openviking_context = context_text

    # Append to system prompt as a variable block
    if ctx.system_prompt:
        ctx.system_prompt = ctx.system_prompt + "\n\n" + context_text
    else:
        ctx.system_prompt = context_text

    return ctx
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_openviking_processor.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add context_pipeline/openviking_processor.py tests/test_openviking_processor.py
git commit -m "feat: add OpenViking context enrichment processor (Stage 6)"
```

---

### Task 5: Register Stage 6 in Pipeline Factory

**Files:**
- Modify: `D:\QWEN3.0\context_pipeline\factory.py`
- Modify: `D:\QWEN3.0\tests\test_context_pipeline.py`

- [ ] **Step 1: Update stage count test**

In `D:\QWEN3.0\tests\test_context_pipeline.py`, modify `test_default_pipeline_processes_full_request`:
Change `assert len(ctx.processors_applied) == 5` to `== 6`, and update the expected list:
```python
    assert len(ctx.processors_applied) == 6
    assert ctx.processors_applied == [
        "ide_detection",
        "scenario_classification",
        "code_context",
        "prompt_composition",
        "cache_optimization",
        "openviking_context",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_context_pipeline.py::test_default_pipeline_processes_full_request -v`
Expected: FAIL — `processors_applied` has 5 items, not 6

- [ ] **Step 3: Register processor in factory**

In `D:\QWEN3.0\context_pipeline\factory.py`, add import:
```python
from .openviking_processor import openviking_context_processor
```

And add to the pipeline chain after `cache_optimization`:
```python
        .add("openviking_context", openviking_context_processor)
```

Full updated factory:
```python
"""Default pipeline factory for LiMa request processing."""

from .pipeline import Pipeline
from .processors import (
    cache_optimization_processor,
    code_context_processor,
    ide_detection_processor,
    prompt_composition_processor,
    scenario_classification_processor,
)
from .openviking_processor import openviking_context_processor


def build_default_pipeline() -> Pipeline:
    """Build the standard LiMa context processing pipeline.

    Stage order matters — each processor builds on previous outputs:
    1. IDE Detection → populates ctx.ide
    2. Scenario Classification → populates ctx.scenario (uses ctx.ide)
    3. Code Context → populates ctx.code_context (uses ctx.scenario)
    4. Prompt Composition → populates ctx.system_prompt (uses all above)
    5. Cache Optimization → reorders ctx.system_prompt for prefix caching
    6. OpenViking Context → enriches ctx.system_prompt with Viking retrieval
    """
    return (
        Pipeline()
        .add("ide_detection", ide_detection_processor)
        .add("scenario_classification", scenario_classification_processor)
        .add("code_context", code_context_processor)
        .add("prompt_composition", prompt_composition_processor)
        .add("cache_optimization", cache_optimization_processor)
        .add("openviking_context", openviking_context_processor)
    )
```

- [ ] **Step 4: Run all context pipeline tests**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_context_pipeline.py tests/test_openviking_processor.py -v`
Expected: All pass (including updated stage count assertion)

- [ ] **Step 5: Commit**

```bash
git add context_pipeline/factory.py tests/test_context_pipeline.py
git commit -m "feat: register OpenViking processor as Stage 6 in pipeline"
```

---

### Task 6: L0/L1/L2 Tiered Skill Loading

**Files:**
- Create: `D:\QWEN3.0\skills_tier_builder.py`
- Modify: `D:\QWEN3.0\skills_injector.py`
- Test: `D:\QWEN3.0\tests\test_skills_tiered.py`

- [ ] **Step 1: Write failing tests for tiered loading**

Create `D:\QWEN3.0\tests\test_skills_tiered.py`:
```python
"""Tests for L0/L1/L2 tiered skill loading."""
import os
import tempfile
import pytest

from skills_injector import load_skills_from_dir, _trim_to_budget


def test_skill_with_sidecar_abstract(tmp_path):
    """A skill with .abstract sidecar gets abstract field populated."""
    skill_dir = tmp_path / "code"
    skill_dir.mkdir()

    # Main skill file
    (skill_dir / "error_handling.md").write_text(
        "---\nid: error_handling\ncategory: code\n---\n"
        "Full error handling skill content with detailed instructions.",
        encoding="utf-8",
    )
    # L0 abstract sidecar
    (skill_dir / "error_handling.abstract").write_text(
        "Error handling patterns and retry strategies.",
        encoding="utf-8",
    )

    skills = load_skills_from_dir(str(tmp_path))
    assert len(skills) == 1
    assert skills[0]["abstract"] == "Error handling patterns and retry strategies."


def test_skill_without_sidecar_has_empty_abstract(tmp_path):
    """A skill without .abstract sidecar gets empty abstract."""
    skill_dir = tmp_path / "code"
    skill_dir.mkdir()
    (skill_dir / "logging.md").write_text(
        "---\nid: logging\ncategory: code\n---\nLogging best practices.",
        encoding="utf-8",
    )

    skills = load_skills_from_dir(str(tmp_path))
    assert len(skills) == 1
    assert skills[0]["abstract"] == ""


def test_tier_selection_by_budget(tmp_path):
    """When budget is tight, L0 (abstract) is used; otherwise L2 (full)."""
    from skills_injector import select_skill_tier

    skill = {
        "id": "test",
        "abstract": "Short summary",
        "content": "Very long detailed content " * 50,
    }

    # Tight budget → L0
    tier_text = select_skill_tier(skill, max_tokens=30)
    assert tier_text == "Short summary"

    # Generous budget → L2 (full content)
    tier_text = select_skill_tier(skill, max_tokens=500)
    assert "Very long detailed content" in tier_text


def test_tier_falls_back_to_content_when_no_abstract():
    """If abstract is empty, fall back to truncated content even on tight budget."""
    from skills_injector import select_skill_tier

    skill = {"id": "test", "abstract": "", "content": "Some content here"}
    tier_text = select_skill_tier(skill, max_tokens=30)
    assert "Some content" in tier_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_skills_tiered.py -v`
Expected: FAIL — `select_skill_tier` not defined, `abstract` key missing

- [ ] **Step 3: Add sidecar loading to `load_skills_from_dir`**

In `D:\QWEN3.0\skills_injector.py`, modify the `load_skills_from_dir` function.
After `skills.append({...})`, add abstract loading. Replace the `skills.append` block with:

```python
            # Load L0 abstract sidecar if present
            abstract_path = fpath.rsplit(".", 1)[0] + ".abstract"
            abstract = ""
            if os.path.exists(abstract_path):
                try:
                    with open(abstract_path, encoding="utf-8") as af:
                        abstract = af.read().strip()
                except Exception:
                    pass

            skills.append({
                "id": meta["id"],
                "category": meta.get("category", "general"),
                "content": body,
                "abstract": abstract,
                "detect_keywords": meta.get("detect_keywords", []),
                "always_apply": meta.get("always_apply", False),
                "priority": meta.get("priority", 5),
                "globs": meta.get("globs", []),
            })
```

- [ ] **Step 4: Add `select_skill_tier` function**

Add to `D:\QWEN3.0\skills_injector.py` (after `_trim_to_budget`):
```python
def select_skill_tier(skill: dict, max_tokens: int = 200) -> str:
    """Select appropriate tier based on token budget.

    L0 (abstract): ~30 tokens — one-line summary for quick scanning
    L2 (content): full skill body — when budget allows

    Falls back to truncated L2 if L0 is empty.
    """
    abstract = skill.get("abstract", "")
    content = skill.get("content", "")
    max_chars = max_tokens * CHARS_PER_TOKEN

    # L0: use abstract if budget is tight and abstract exists
    if max_tokens <= 50 and abstract:
        return abstract[:max_chars]

    # L2: use full content, trimmed to budget
    return _trim_to_budget(content, max_tokens)
```

- [ ] **Step 5: Run tiered skill tests**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_skills_tiered.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add skills_injector.py tests/test_skills_tiered.py
git commit -m "feat: add L0/L1/L2 tiered skill loading with abstract sidecars"
```

---

### Task 7: Skill Tier Builder CLI Utility

**Files:**
- Create: `D:\QWEN3.0\skills_tier_builder.py`

- [ ] **Step 1: Write the builder script**

Create `D:\QWEN3.0\skills_tier_builder.py`:
```python
"""CLI utility to generate L0 (.abstract) sidecars for all skills.

Usage:
    python skills_tier_builder.py [--skills-dir skills/] [--dry-run]

Reads each skill .md file, extracts the first non-empty line after
frontmatter as the L0 abstract, and writes a .abstract sidecar file.
"""
import argparse
import glob
import os
import sys


def extract_abstract(content: str) -> str:
    """Extract first meaningful line after YAML frontmatter as abstract."""
    # Skip frontmatter
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + 4:]

    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            # Strip markdown heading markers
            line = line.lstrip("#").strip()
        if len(line) > 10:
            return line[:200]
    return ""


def build_sidecars(skills_dir: str, dry_run: bool = False) -> int:
    """Generate .abstract sidecars for all skill files. Returns count."""
    pattern = os.path.join(skills_dir, "**", "*.md")
    count = 0
    for fpath in glob.glob(pattern, recursive=True):
        with open(fpath, encoding="utf-8") as f:
            raw = f.read()

        abstract = extract_abstract(raw)
        if not abstract:
            print(f"  SKIP (no abstract): {fpath}")
            continue

        abstract_path = fpath.rsplit(".", 1)[0] + ".abstract"
        if dry_run:
            print(f"  WOULD WRITE: {abstract_path}")
            print(f"    → {abstract}")
        else:
            with open(abstract_path, "w", encoding="utf-8") as f:
                f.write(abstract)
            print(f"  WROTE: {abstract_path}")
        count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate L0 abstract sidecars for LiMa skills")
    parser.add_argument("--skills-dir", default=os.path.join(os.path.dirname(__file__), "skills"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = build_sidecars(args.skills_dir, dry_run=args.dry_run)
    print(f"\n{'Would generate' if args.dry_run else 'Generated'} {n} abstract sidecar(s)")
```

- [ ] **Step 2: Run dry-run to preview**

Run: `cd D:\QWEN3.0 && python skills_tier_builder.py --dry-run`
Expected: Lists skill files with their extracted abstracts

- [ ] **Step 3: Generate actual sidecars**

Run: `cd D:\QWEN3.0 && python skills_tier_builder.py`
Expected: `.abstract` files created alongside each `.md` skill file

- [ ] **Step 4: Commit**

```bash
git add skills_tier_builder.py skills/
git commit -m "feat: add skill tier builder CLI and generate L0 abstracts"
```

---

### Task 8: Integration Test — Full Pipeline with OpenViking

**Files:**
- Modify: `D:\QWEN3.0\tests\test_context_pipeline.py`

- [ ] **Step 1: Add integration test**

Append to `D:\QWEN3.0\tests\test_context_pipeline.py`:
```python
def test_full_pipeline_with_openviking_disabled():
    """Pipeline works normally when OpenViking is disabled (default)."""
    import os
    os.environ.pop("LIMA_OPENVIKING_ENABLED", None)
    pipe = build_default_pipeline()
    ctx = RequestContext(
        headers={"user-agent": "opencode/1.0"},
        messages=[{"role": "user", "content": "fix the auth bug"}],
        path="/v1/chat/completions",
    )
    ctx = pipe.process(ctx)

    assert ctx.ide == "OpenCode"
    assert ctx.scenario == "coding"
    assert "openviking_context" in ctx.processors_applied
    assert ctx.openviking_context == ""  # disabled = empty
    assert "编程助手" in ctx.system_prompt
```

- [ ] **Step 2: Run full pipeline test**

Run: `cd D:\QWEN3.0 && python -m pytest tests/test_context_pipeline.py -v`
Expected: All pass (including new integration test)

- [ ] **Step 3: Commit**

```bash
git add tests/test_context_pipeline.py
git commit -m "test: add OpenViking integration test (disabled path)"
```

---

### Task 9: Final Verification and Documentation

- [ ] **Step 1: Run full test suite to check for regressions**

Run: `cd D:\QWEN3.0 && python -m pytest tests/ -v --timeout=30 -x`
Expected: All tests pass, no regressions

- [ ] **Step 2: Update context_pipeline docstring**

In `D:\QWEN3.0\context_pipeline\__init__.py`, update the module docstring:
```python
"""Context Pipeline ordered processor chain inspired by Google ADK.

Each processor transforms a RequestContext through a defined stage:
1. IDE Detection: identify client environment
2. Scenario Classification: coding/chat/vision
3. Code Context: semantic search for relevant files
4. Prompt Composition: build structured system prompt (vibe-coding layers)
5. Cache Optimization: stable prefix for model prefix caching
6. OpenViking Context: enrich with Viking knowledge retrieval (optional)
"""
```

- [ ] **Step 3: Final commit**

```bash
git add context_pipeline/__init__.py
git commit -m "docs: update pipeline docstring with Stage 6"
```
