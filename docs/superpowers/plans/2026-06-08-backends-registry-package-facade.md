# Backends Registry Package Facade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the split backend registry package while removing the dirty deleted-file state for the historical `backends_registry.py` path.

**Architecture:** Keep `backends_registry/` as the runtime authority because Python imports the package before the same-name `.py` module. Restore `backends_registry.py` as a small compatibility note and tighten the package entry point by replacing mojibake comments with clear ASCII comments and logged overlay failures.

**Tech Stack:** Python 3.10, module/package import resolution, ruff, pytest.

---

### Task 1: Restore Historical Registry Path Without Changing Runtime Imports

**Files:**
- Create: `backends_registry.py`
- Modify: `backends_registry/__init__.py`
- Test: import smoke and focused backend registry tests

- [x] **Step 1: Verify import precedence**

Run:

```text
.\.venv310\Scripts\python.exe -c "import backends_registry; print(backends_registry.__file__)"
```

Expected: import resolves to `backends_registry\__init__.py`.

- [x] **Step 2: Restore `backends_registry.py` as a compatibility note**

The file documents that the package is the runtime authority and prevents the working tree from representing the old module path as deleted.

- [x] **Step 3: Clean package entry point comments and overlay error handling**

Replace mojibake comments with ASCII text and log JSON/OSError overlay failures instead of returning silently.

- [x] **Step 4: Run focused verification**

Run:

```text
.\.venv310\Scripts\python.exe -m ruff check backends_registry.py backends_registry\__init__.py
.\.venv310\Scripts\python.exe -c "import backends_registry; print(backends_registry.__file__); print(len(backends_registry.BACKENDS))"
```

Expected: ruff passes; import resolves to the package; backend count is nonzero.

- [x] **Step 5: Track package entry points despite `_*.py` ignore**

Add `!**/__init__.py` after the one-off `_*.py` ignore rule so split package entry files are not accidentally excluded from commits.
