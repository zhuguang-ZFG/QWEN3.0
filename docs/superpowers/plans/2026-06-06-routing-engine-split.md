# Routing Engine Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `routing_engine.py` below the project 300-line target without changing its public API or route behavior.

**Architecture:** Keep `routing_engine.route()` as the authoritative public entry point and move cohesive helper blocks into focused modules. Preserve compatibility re-exports and existing test monkeypatch points by passing dependencies from `routing_engine.py` into helper functions instead of importing those dependencies directly inside helpers when tests patch them.

**Tech Stack:** Python 3.10, FastAPI request-path modules, pytest, ruff.

---

## File Structure

- Create: `routing_engine_types.py`
- Responsibility: Own `RouteResult` dataclass only.

- Create: `routing_engine_response.py`
- Responsibility: Own response construction and context-injection trace closeout.

- Create: `routing_engine_skills.py`
- Responsibility: Own skill injection wrapper and injected skill ID detection.

- Create: `routing_engine_context.py`
- Responsibility: Own retrieval, enrichment, web search, coding code-context, complexity assessment, and early skills injection.

- Create: `routing_engine_opencode.py`
- Responsibility: Own OpenCode coding-path prompt injection before `code_orchestrator`.

- Modify: `routing_engine.py`
- Responsibility: Remain the stable public facade and route orchestrator. Keep `route()`, public imports, `__all__`, and monkeypatch-friendly names: `inject_retrieval_context`, `classify_scenario`, `select`, `health_tracker`.

- Modify: `tests/test_routing_engine.py`
- Responsibility: Add focused import/re-export guards for the split modules and keep existing route regression tests unchanged.

---

### Task 1: Add Split Module Import Guards

**Files:**
- Modify: `tests/test_routing_engine.py`

- [ ] **Step 1: Add failing tests for new module boundaries**

Add these tests near the existing route tests in `tests/test_routing_engine.py`:

```python
def test_routing_engine_reexports_route_result_after_split():
    result = re_.RouteResult(backend="unit", answer="ok")
    assert result.backend == "unit"
    assert result.answer == "ok"


def test_routing_engine_helper_modules_import():
    import routing_engine_context
    import routing_engine_opencode
    import routing_engine_response
    import routing_engine_skills
    import routing_engine_types

    assert hasattr(routing_engine_types, "RouteResult")
    assert hasattr(routing_engine_response, "respond")
    assert hasattr(routing_engine_skills, "inject_skills")
    assert hasattr(routing_engine_context, "prepare_route_context")
    assert hasattr(routing_engine_opencode, "inject_coding_opencode_prompts")
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_routing_engine_helper_modules_import tests/test_routing_engine.py::test_routing_engine_reexports_route_result_after_split -v`

Expected: `test_routing_engine_helper_modules_import` fails with `ModuleNotFoundError` for at least one new module.

- [ ] **Step 3: Do not commit yet**

Expected: Tests are red and implementation has not started.

---

### Task 2: Extract RouteResult

**Files:**
- Create: `routing_engine_types.py`
- Modify: `routing_engine.py`

- [ ] **Step 1: Create `routing_engine_types.py`**

```python
"""Shared routing engine dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RouteResult:
    backend: str = ""
    answer: str = ""
    request_type: str = "chat"
    scenario: str = ""
    ms: int = 0
    fallback_used: bool = False
    skills_injected: list = field(default_factory=list)
    retrieval_context: str = ""
    usage: dict | None = None
    injection_meta: dict = field(default_factory=dict)
```

- [ ] **Step 2: Update imports in `routing_engine.py`**

Remove this import:

```python
from dataclasses import dataclass, field
```

Add this import:

```python
from routing_engine_types import RouteResult
```

Remove the inline `RouteResult` dataclass from `routing_engine.py`.

- [ ] **Step 3: Run focused tests**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_routing_engine_reexports_route_result_after_split tests/test_routing_engine.py::test_route_result_has_retrieval_context_field -v`

Expected: Both tests pass.

- [ ] **Step 4: Commit**

```powershell
git add routing_engine.py routing_engine_types.py tests/test_routing_engine.py
git commit -m "refactor: extract routing result type"
```

---

### Task 3: Extract Response Helpers

**Files:**
- Create: `routing_engine_response.py`
- Modify: `routing_engine.py`

- [ ] **Step 1: Create `routing_engine_response.py`**

```python
"""Response helpers for routing_engine."""

from __future__ import annotations

from response_builder import build_anthropic_response, build_response, make_chat_id
from routing_engine_types import RouteResult


def respond(result: RouteResult, fmt: str = "openai", model: str = "lima-1.3") -> dict:
    chat_id = make_chat_id()
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, result.answer, result.backend, model)
    resp = build_response(chat_id, result.answer, result.backend, result.ms, usage=result.usage)
    resp["x_lima_meta"]["request_type"] = result.request_type
    resp["x_lima_meta"]["skills_injected"] = result.skills_injected
    return resp


def with_injection_meta(result: RouteResult, backend: str = "") -> RouteResult:
    try:
        from context_injection_trace import finish_trace

        trace = finish_trace(backend=backend)
        if trace:
            result.injection_meta = trace.to_meta()
    except ImportError:
        pass
    return result
```

- [ ] **Step 2: Update `routing_engine.py` imports and call sites**

Remove this import:

```python
from response_builder import build_anthropic_response, build_response, make_chat_id
```

Add this import:

```python
from routing_engine_response import respond, with_injection_meta as _with_injection_meta
```

Delete the inline `respond()` and `_with_injection_meta()` definitions from `routing_engine.py`.

- [ ] **Step 3: Run focused tests**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_routing_engine_helper_modules_import tests/test_routing_engine.py::test_route_e2e_chat -v`

Expected: Both tests pass.

- [ ] **Step 4: Commit**

```powershell
git add routing_engine.py routing_engine_response.py tests/test_routing_engine.py
git commit -m "refactor: extract routing response helpers"
```

---

### Task 4: Extract Skill Helpers

**Files:**
- Create: `routing_engine_skills.py`
- Modify: `routing_engine.py`

- [ ] **Step 1: Create `routing_engine_skills.py`**

```python
"""Skill injection helpers for routing_engine."""

from __future__ import annotations

import skills_injector as skills_mod


def inject_skills(messages: list[dict], *, backend: str = "", ide_source: str = "", system_prompt: str = "") -> list[dict]:
    """Inject backend-aware skills for IDE and coding requests."""
    return skills_mod.apply_skills(
        backend=backend,
        messages=messages,
        system_prompt=system_prompt,
        ide_source=ide_source,
    )


def get_injected_ids(original: list[dict], modified: list[dict]) -> list[str]:
    """Extract injected skill IDs from the additional system prompt."""
    if len(modified) <= len(original):
        return []
    for msg in modified:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if "Available skills:" in content:
                names = content.replace("Available skills:", "").strip()
                return ["dir:" + name.strip() for name in names.split(",") if name.strip()]
    extra = len(modified) - len(original)
    return [f"injected_{extra}_skills"] if extra > 0 else []
```

- [ ] **Step 2: Update `routing_engine.py` imports and call sites**

Remove this import:

```python
import skills_injector as skills_mod
```

Add this import:

```python
from routing_engine_skills import get_injected_ids as _get_injected_ids, inject_skills
```

Delete the inline `inject_skills()` and `_get_injected_ids()` definitions from `routing_engine.py`.

- [ ] **Step 3: Run focused tests**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_routing_engine_helper_modules_import tests/test_routing_engine.py::test_route_e2e_chat tests/test_routing_engine.py::test_route_e2e_ide_no_floor -v`

Expected: All selected tests pass.

- [ ] **Step 4: Commit**

```powershell
git add routing_engine.py routing_engine_skills.py tests/test_routing_engine.py
git commit -m "refactor: extract routing skill helpers"
```

---

### Task 5: Extract Context Preparation

**Files:**
- Create: `routing_engine_context.py`
- Modify: `routing_engine.py`

- [ ] **Step 1: Create `routing_engine_context.py`**

```python
"""Context preparation helpers for routing_engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PreparedRouteContext:
    messages: list[dict]
    retrieval_text: str = ""
    recalled_backend: str = ""
    injected_ids: list[str] = field(default_factory=list)


def begin_injection_trace(*, scenario: str, request_type: str) -> None:
    try:
        from context_injection_trace import begin_trace

        begin_trace(scenario=scenario, request_type=request_type)
    except ImportError:
        pass


def prepare_route_context(
    query: str,
    messages: list[dict],
    *,
    scenario: str,
    request_type: str,
    ide_source: str,
    system_prompt: str,
    client_ip: str,
    user_agent: str,
    retrieval_injector: Callable[[list[dict]], tuple[list[dict], str]],
    skills_injector: Callable[..., list[dict]],
    injected_id_getter: Callable[[list[dict], list[dict]], list[str]],
) -> PreparedRouteContext:
    begin_injection_trace(scenario=scenario, request_type=request_type)
    recalled_backend = _recall_backend(messages, scenario)
    messages, retrieval_text = retrieval_injector(messages)
    _record_retrieval(retrieval_text)
    messages = _inject_enriched_context(messages, client_ip=client_ip, user_agent=user_agent)
    messages, retrieval_text = _inject_web_search(query, messages, retrieval_text)
    messages = _inject_code_context(query, messages, scenario)
    _assess_complexity(messages, ide_source=ide_source)

    count_before = len(messages)
    try:
        messages = skills_injector(messages, backend="", ide_source=ide_source, system_prompt=system_prompt)
    except Exception as exc:
        logging.warning("[SKILLS] early injection failed: %s: %s", type(exc).__name__, exc)

    injected_ids = injected_id_getter(list(messages[:count_before]), messages)
    _record_skills(injected_ids)
    return PreparedRouteContext(
        messages=messages,
        retrieval_text=retrieval_text,
        recalled_backend=recalled_backend,
        injected_ids=injected_ids,
    )


def _recall_backend(messages: list[dict], scenario: str) -> str:
    try:
        from context_pipeline.skill_store import get_skill_store

        recalled = get_skill_store().recall(messages, scenario)
        return recalled.backend if recalled else ""
    except ImportError as exc:
        logging.debug("routing_engine: skill_store not available: %s", exc)
    return ""


def _record_retrieval(retrieval_text: str) -> None:
    try:
        from context_injection_trace import record_retrieval

        record_retrieval(retrieval_text)
    except ImportError:
        pass


def _inject_enriched_context(messages: list[dict], *, client_ip: str, user_agent: str) -> list[dict]:
    try:
        from context_pipeline.enrich_context import inject_enriched_context

        return inject_enriched_context(messages, client_ip=client_ip, user_agent=user_agent)
    except Exception as exc:
        logging.debug("routing_engine: enrich_context injection failed: %s", exc)
    return messages


def _inject_web_search(query: str, messages: list[dict], retrieval_text: str) -> tuple[list[dict], str]:
    try:
        from context_pipeline.web_search_context import inject_web_search_context

        messages, web_search_text = inject_web_search_context(query, messages)
        if web_search_text:
            retrieval_text = (retrieval_text + "\n" + web_search_text).strip()
            try:
                from context_injection_trace import record_web_search

                record_web_search(web_search_text)
            except ImportError:
                pass
    except Exception as exc:
        logging.debug("routing_engine: web_search_context injection failed: %s", exc)
    return messages, retrieval_text


def _inject_code_context(query: str, messages: list[dict], scenario: str) -> list[dict]:
    if scenario != "coding":
        return messages
    try:
        from context_pipeline.code_context_injection import scan_and_build_context

        code_context_text = scan_and_build_context(query, messages)
        if not code_context_text:
            return messages
        code_context_message = {"role": "system", "content": code_context_text}
        if messages and messages[0].get("role") == "system":
            messages.insert(1, code_context_message)
        else:
            messages.insert(0, code_context_message)
        try:
            from context_injection_trace import record_code_context

            record_code_context(code_context_text)
        except ImportError:
            pass
    except Exception as exc:
        logging.debug("code_context_injection failed: %s", exc)
    return messages


def _assess_complexity(messages: list[dict], *, ide_source: str) -> None:
    try:
        from context_pipeline.complexity import assess_complexity

        raw_messages = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            if isinstance(m, dict)
            else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
            for m in messages
        ]
        assess_complexity(raw_messages, ide=ide_source)
    except ImportError as exc:
        logging.debug("routing_engine: complexity assessment not available: %s", exc)


def _record_skills(injected_ids: list[str]) -> None:
    try:
        from context_injection_trace import record_skills

        record_skills(injected_ids)
    except ImportError:
        pass
```

- [ ] **Step 2: Update `routing_engine.py` to use `prepare_route_context()`**

Add this import:

```python
from routing_engine_context import prepare_route_context
```

Replace the block from `begin_trace(...)` through `record_skills(_injected_ids)` with:

```python
    prepared = prepare_route_context(
        query,
        messages,
        scenario=scenario,
        request_type=req_type,
        ide_source=ide_source,
        system_prompt=system_prompt,
        client_ip=client_ip,
        user_agent=user_agent,
        retrieval_injector=inject_retrieval_context,
        skills_injector=inject_skills,
        injected_id_getter=_get_injected_ids,
    )
    messages = prepared.messages
    _retrieval_text = prepared.retrieval_text
    _recalled_backend = prepared.recalled_backend
    _injected_ids = prepared.injected_ids
```

This preserves `tests/test_routing_engine.py::test_route_uses_shared_retrieval_injection`, because the route function passes the monkeypatched `routing_engine.inject_retrieval_context` into the helper.

- [ ] **Step 3: Run focused context tests**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_route_uses_shared_retrieval_injection tests/test_routing_engine.py::test_skill_store_recall_uses_real_scenario tests/test_routing_engine.py::test_route_e2e_chat -v`

Expected: All selected tests pass.

- [ ] **Step 4: Commit**

```powershell
git add routing_engine.py routing_engine_context.py tests/test_routing_engine.py
git commit -m "refactor: extract routing context preparation"
```

---

### Task 6: Extract OpenCode Coding Prompt Injection

**Files:**
- Create: `routing_engine_opencode.py`
- Modify: `routing_engine.py`

- [ ] **Step 1: Create `routing_engine_opencode.py`**

```python
"""OpenCode prompt injection helpers for routing_engine coding path."""

from __future__ import annotations

import logging
from typing import Callable


def inject_coding_opencode_prompts(
    messages: list[dict],
    *,
    system_prompt: str,
    tools: list[dict] | None,
    headers: dict,
    needs_tools: bool,
    ide_source: str,
    health_map_getter: Callable[[], dict],
    selector: Callable[..., list[str]],
) -> list[dict]:
    try:
        from opencode_tool_aware import inject_opencode_prompt

        messages = inject_opencode_prompt(
            messages,
            backend="",
            system_prompt=system_prompt,
            tools=tools,
            headers=headers,
        )
    except (ImportError, Exception) as exc:
        logging.debug("routing_engine: opencode_tool_aware failed: %s", exc)

    try:
        estimated_backend = _estimate_backend(
            needs_tools=needs_tools,
            ide_source=ide_source,
            health_map_getter=health_map_getter,
            selector=selector,
        )
        if estimated_backend:
            messages = _inject_reasoning_bridge(messages, estimated_backend)
            messages = _inject_sequential_tool_hint(messages, estimated_backend, tools)
    except (ImportError, Exception) as exc:
        logging.debug("routing_engine: reasoning_bridge failed: %s", exc)

    return messages


def _estimate_backend(
    *,
    needs_tools: bool,
    ide_source: str,
    health_map_getter: Callable[[], dict],
    selector: Callable[..., list[str]],
) -> str:
    try:
        candidates = selector(
            "ide",
            health_map_getter(),
            scenario="coding",
            needs_tools=needs_tools,
            ide_source=ide_source,
        )
        return candidates[0] if candidates else ""
    except Exception:
        return ""


def _inject_reasoning_bridge(messages: list[dict], backend: str) -> list[dict]:
    from opencode_reasoning_bridge import inject_thinking_reminder, select_provider_system_prompt

    messages = inject_thinking_reminder(messages, backend)
    provider_hint = select_provider_system_prompt(backend)
    if not provider_hint:
        return messages
    system_index = next((i for i, msg in enumerate(messages) if msg.get("role") == "system"), -1)
    if system_index >= 0:
        old_content = messages[system_index].get("content", "")
        if isinstance(old_content, str):
            messages[system_index] = {
                **messages[system_index],
                "content": old_content.rstrip() + "\n" + provider_hint,
            }
    return messages


def _inject_sequential_tool_hint(
    messages: list[dict],
    backend: str,
    tools: list[dict] | None,
) -> list[dict]:
    try:
        from opencode_tool_splitter import build_sequential_tool_prompt, should_inject_sequential_hint

        if not should_inject_sequential_hint(backend):
            return messages
        sequential_hint = build_sequential_tool_prompt(tools)
        if not sequential_hint:
            return messages
        system_index = next((i for i, msg in enumerate(messages) if msg.get("role") == "system"), -1)
        if system_index >= 0:
            old_content = messages[system_index].get("content", "")
            if isinstance(old_content, str):
                messages[system_index] = {
                    **messages[system_index],
                    "content": old_content.rstrip() + "\n" + sequential_hint,
                }
        else:
            messages.insert(0, {"role": "system", "content": sequential_hint})
    except (ImportError, Exception) as exc:
        logging.debug("routing_engine: tool_splitter hint failed: %s", exc)
    return messages
```

- [ ] **Step 2: Update `routing_engine.py` coding branch**

Add this import:

```python
from routing_engine_opencode import inject_coding_opencode_prompts
```

Inside the `if scenario == "coding" and call_fn:` block, replace the nested OpenCode prompt injection block before `import code_orchestrator` with:

```python
            messages = inject_coding_opencode_prompts(
                messages,
                system_prompt=system_prompt,
                tools=tools,
                headers=headers or {},
                needs_tools=needs_tools,
                ide_source=ide_source,
                health_map_getter=health_tracker.get_health_map,
                selector=select,
            )
```

This preserves route tests that monkeypatch `routing_engine.select`, because `route()` passes the patched selector into the helper.

- [ ] **Step 3: Run focused OpenCode/coding tests**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_route_e2e_ide_no_floor tests/test_opencode_tool_routing.py tests/test_opencode_system_prompt.py -q --tb=short`

Expected: All selected tests pass.

- [ ] **Step 4: Commit**

```powershell
git add routing_engine.py routing_engine_opencode.py tests/test_routing_engine.py
git commit -m "refactor: extract opencode routing prompts"
```

---

### Task 7: Verify File Size and Full Routing Tests

**Files:**
- Modify: `routing_engine.py`
- Modify: `docs/superpowers/plans/2026-06-06-routing-engine-split.md` only if execution notes are added.

- [ ] **Step 1: Check `routing_engine.py` line count**

Run: `.venv310\Scripts\python.exe -c "from pathlib import Path; print(len(Path('routing_engine.py').read_text(encoding='utf-8').splitlines()))"`

Expected: Output is less than `300`.

- [ ] **Step 2: Run routing regression suite**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py -q --tb=short`

Expected: All tests in `tests/test_routing_engine.py` pass.

- [ ] **Step 3: Run nearby OpenCode and pipeline tests**

Run: `.venv310\Scripts\python.exe -m pytest tests/test_chat_ide_golden_path.py tests/test_opencode_tool_routing.py tests/test_opencode_system_prompt.py tests/test_request_pipeline_authority.py -q --tb=short`

Expected: All selected tests pass.

- [ ] **Step 4: Run lint/format check for touched files**

Run: `.venv310\Scripts\python.exe -m ruff check routing_engine.py routing_engine_types.py routing_engine_response.py routing_engine_skills.py routing_engine_context.py routing_engine_opencode.py tests/test_routing_engine.py`

Expected: Ruff exits with code `0`.

- [ ] **Step 5: Run diff whitespace check**

Run: `git diff --check`

Expected: No output and exit code `0`.

- [ ] **Step 6: Commit verification cleanup**

```powershell
git add routing_engine.py routing_engine_types.py routing_engine_response.py routing_engine_skills.py routing_engine_context.py routing_engine_opencode.py tests/test_routing_engine.py
git commit -m "test: guard routing engine split"
```

---

## Self-Review

**Spec coverage:** This plan addresses the agreed optimization direction: split `routing_engine.py`, keep `route()` stable, preserve existing monkeypatch points, and verify with route/OpenCode/pipeline tests.

**Placeholder scan:** No `TBD`, `TODO`, or unspecified implementation steps remain. Each task includes exact files, code snippets, commands, and expected outcomes.

**Type consistency:** `RouteResult`, `PreparedRouteContext`, `respond`, `with_injection_meta`, `inject_skills`, `get_injected_ids`, `prepare_route_context`, and `inject_coding_opencode_prompts` are named consistently across tasks and imports.
