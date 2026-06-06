# Backend-Aware Skill Reinjection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make routing skill reinjection backend-aware without duplicating early weak-model skill prompts.

**Architecture:** `routing_engine_context.inject_all_context()` still performs an early backend-unknown skill pass so context traces remain populated. After backend selection, `routing_engine.route()` calls `routing_engine_skills.apply_backend_aware_skills()` with the selected backend. This slice tags LiMa-generated skill prompts with `## LiMa Skills`, then makes the second pass remove only tagged prior skill prompts before applying the backend-specific mode.

**Tech Stack:** Python 3.10, FastAPI routing stack, pytest, ruff.

---

### Task 1: Lock Backend-Aware Reinjection Semantics

**Files:**
- Modify: `tests/test_routing_engine.py`
- Modify: `tests/test_skills_injector.py`
- Modify: `skills_injector.py`
- Modify: `routing_engine_skills.py`

- [ ] **Step 1: Add a failing unit test for strong-backend replacement**

Append this test near existing skill injection tests in `tests/test_routing_engine.py`:

```python
def test_apply_backend_aware_skills_replaces_early_weak_prompt_for_strong_backend():
    from routing_engine_skills import apply_backend_aware_skills

    early_messages = re_.inject_skills(
        [{"role": "user", "content": "help"}],
        backend="",
        ide_source="",
        system_prompt="",
    )
    result = apply_backend_aware_skills(
        early_messages,
        "longcat_chat",
        ide_source="",
        system_prompt="",
    )

    system_texts = [
        m.get("content", "")
        for m in result
        if m.get("role") == "system" and isinstance(m.get("content"), str)
    ]
    assert sum("Available skills:" in text for text in system_texts) == 1
    assert not any("Never fabricate" in text for text in system_texts)
```

- [ ] **Step 2: Add a failing unit test for weak-backend non-duplication**

Append this test immediately after the strong-backend test:

```python
def test_apply_backend_aware_skills_does_not_duplicate_weak_skill_prompt():
    from routing_engine_skills import apply_backend_aware_skills

    early_messages = re_.inject_skills(
        [{"role": "user", "content": "help"}],
        backend="",
        ide_source="",
        system_prompt="",
    )
    result = apply_backend_aware_skills(
        early_messages,
        "chat_ubi",
        ide_source="",
        system_prompt="",
    )

    system_texts = [
        m.get("content", "")
        for m in result
        if m.get("role") == "system" and isinstance(m.get("content"), str)
    ]
    assert sum("Never fabricate" in text for text in system_texts) <= 1
    assert len(result) == len(early_messages)
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_apply_backend_aware_skills_replaces_early_weak_prompt_for_strong_backend tests/test_routing_engine.py::test_apply_backend_aware_skills_does_not_duplicate_weak_skill_prompt -q --tb=short
```

Expected before implementation: at least one assertion fails because the backend-aware pass appends a second skill system prompt.

- [ ] **Step 4: Tag generated skill prompts**

In `skills_injector.py`, add a marker constant and prefix both injection modes:

```python
SKILL_PROMPT_MARKER = "## LiMa Skills"
```

Weak injection mode:

```python
skills_msg = {"role": "system", "content": f"{SKILL_PROMPT_MARKER}\n{skills_text}"}
```

Strong directory mode:

```python
dir_msg = {"role": "system", "content": f"{SKILL_PROMPT_MARKER}\nAvailable skills: {names}"}
```

- [ ] **Step 5: Implement skill prompt stripping**

In `routing_engine_skills.py`, add a helper that removes LiMa skill prompts created by `skills_injector`:

```python
def _is_lima_skill_prompt(msg: dict) -> bool:
    if msg.get("role") != "system":
        return False
    content = msg.get("content", "")
    if not isinstance(content, str):
        return False
    return skills_mod.SKILL_PROMPT_MARKER in content


def _without_lima_skill_prompts(messages: list[dict]) -> list[dict]:
    return [msg for msg in messages if not _is_lima_skill_prompt(msg)]
```

Then update `apply_backend_aware_skills()` to call `skills_mod.apply_skills()` with the stripped base:

```python
base_messages = _without_lima_skill_prompts(messages)
return skills_mod.apply_skills(
    backend=backend,
    messages=base_messages,
    system_prompt=system_prompt,
    ide_source=ide_source,
)
```

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py::test_apply_backend_aware_skills_replaces_early_weak_prompt_for_strong_backend tests/test_routing_engine.py::test_apply_backend_aware_skills_does_not_duplicate_weak_skill_prompt tests/test_skills_injector.py -q --tb=short
```

Expected: all selected tests pass.

- [ ] **Step 7: Run lint for touched files**

Run:

```powershell
ruff check routing_engine_skills.py tests/test_routing_engine.py
```

Expected: `All checks passed!`

---

## Self-Review

**Spec coverage:** The plan covers the current issue: second-pass backend-aware skills should use the real backend while avoiding duplicate early prompts.

**Placeholder scan:** No placeholder tasks or unspecified implementation steps remain.

**Type consistency:** All functions use existing `list[dict]` message structures and existing `skills_mod.apply_skills()` signatures.
