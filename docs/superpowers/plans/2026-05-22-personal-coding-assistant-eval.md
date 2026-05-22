# Personal Coding Assistant Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable local evaluation loop that ranks LiMa backends for personal coding-assistant use.

**Architecture:** Keep the first version zero-dependency and repo-native. Coding cases live as JSON fixtures, `coding_eval.py` owns loading/grading/running, and `scripts/eval_coding_backends.py` exposes a CLI that can dry-run candidate selection or call selected backends through `http_caller.call_api`.

**Tech Stack:** Python standard library, existing `backends.py`, existing `http_caller.py`, pytest.

---

## Research Notes

- LiteLLM is a mature AI gateway for 100+ providers and OpenAI-compatible routing, but adopting it now would duplicate much of the existing LiMa router and add operational weight.
- RouteLLM focuses on serving and evaluating LLM routers. Its useful lesson for this project is to separate evaluation data from routing policy.
- promptfoo and OpenAI Evals are strong general eval frameworks. They are better candidates for a later phase after the private coding cases are stable.
- Aider Polyglot is useful as a benchmark direction for real code editing, but the first phase should use smaller fixtures that can run quickly against many unstable/free backends.

## File Structure

| File | Responsibility |
|---|---|
| `coding_eval.py` | Case loading, backend candidate detection, deterministic grading, backend invocation orchestration, report writing. |
| `scripts/eval_coding_backends.py` | CLI entry point for dry-run and real backend evaluation. |
| `evals/coding_cases/*.json` | Small coding prompts with deterministic grading rules. |
| `tests/test_coding_eval.py` | Unit tests for loader, candidate selection, grading, and runner behavior. |
| `docs/CODING_BACKEND_RANKING.md` | Generated or manually refreshed ranking summary. |
| `data/coding_backend_scores.json` | Machine-readable latest score output. |

## Task 1: Coding Eval Core

**Files:**
- Create: `coding_eval.py`
- Test: `tests/test_coding_eval.py`

- [x] **Step 1: Write tests for loading, grading, and candidate detection**

Run: `python -m pytest -q tests/test_coding_eval.py`
Expected before implementation: import failure for `coding_eval`.

- [x] **Step 2: Implement `CodingCase`, `EvalResult`, `load_cases`, `grade_response`, `candidate_backends`, and `run_eval`**

Required signatures:

```python
def load_cases(case_dir: str | Path) -> list[CodingCase]: ...
def grade_response(text: str, case: CodingCase) -> tuple[int, list[str]]: ...
def candidate_backends(backends: dict[str, dict], *, include_unconfigured: bool = False) -> list[str]: ...
def run_eval(cases: list[CodingCase], backends: list[str], call_fn: Callable[[str, list[dict], int], str]) -> list[EvalResult]: ...
```

- [x] **Step 3: Verify tests**

Run: `python -m pytest -q tests/test_coding_eval.py`
Expected: all tests pass.

## Task 2: Coding Case Fixtures

**Files:**
- Create: `evals/coding_cases/python_bugfix.json`
- Create: `evals/coding_cases/json_tool_output.json`
- Create: `evals/coding_cases/code_review.json`

- [x] **Step 1: Add Python bugfix case**

The case checks for a function definition, correct intent, no markdown-only answer, and Python syntax.

- [x] **Step 2: Add JSON/tool-output case**

The case checks that the model can return parseable JSON with required keys and no prose wrapper.

- [x] **Step 3: Add code review case**

The case checks concise bug/risk identification without rewriting unrelated code.

## Task 3: CLI Runner And Reports

**Files:**
- Create: `scripts/eval_coding_backends.py`
- Create/update: `data/coding_backend_scores.json`
- Create/update: `docs/CODING_BACKEND_RANKING.md`

- [x] **Step 1: Add CLI**

Required commands:

```powershell
python scripts/eval_coding_backends.py --dry-run
python scripts/eval_coding_backends.py --backends groq_gptoss,cf_qwen_coder --max-cases 1
```

- [x] **Step 2: Add report writers**

The JSON report contains raw per-case results. The Markdown report lists backend averages and per-case notes.

- [x] **Step 3: Verify dry-run without network**

Run: `python scripts/eval_coding_backends.py --dry-run`
Expected: prints candidate backend names and writes no score file.

## Task 4: First Evidence Loop

**Files:**
- Update: `docs/CODING_BACKEND_RANKING.md`
- Update: `progress.md`

- [x] **Step 1: Run a small smoke eval**

Run only 2-4 likely coding candidates first to avoid rate-limit waste.

Recommended starting set:

```text
groq_gptoss, groq_qwen32b, cf_qwen_coder, mistral_codestral,
nvidia_qwen_coder, or_qwen3_coder, github_codestral, stock_qwen3_coder,
oldllm_gpt41, scnet_ds_pro
```

- [x] **Step 2: Assign preliminary tiers**

Use evidence, not catalog guesses:

```text
fast_coder = lowest latency backend with acceptable score
primary_coder = best score/latency balance
strong_coder = highest score even if slower
fallback_coder = most stable after failures
```

- [x] **Step 3: Update router pool only after evidence exists**

Modify `router_v3.POOLS["code"]` in a separate step after at least one report exists.

Evidence used:

- Broad smoke covered 85 coding-like candidates and found 16 `code_review` passers.
- Full fixture run covered those 16 passers.
- 3/3 passers: `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, `or_gptoss_120b`.
- Fast usable tier: `cerebras_gptoss`, `groq_gptoss`, and `mistral_small` scored 80+ average under 800ms average latency.
- Partial fallback tier: several Mistral variants and `github_codestral` passed code review/Python but failed strict JSON formatting.
- Failure classes included unauthorized keys, rate limits, cooldown, WinError 10013 socket blocks, provider 5xx, and timeouts.
- Follow-up VPS free-model smoke found direct SCNet models working: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, and `scnet_qwen30b`.
- The same VPS smoke found local proxy models down: `scnet_large_ds_flash`/`scnet_large_ds_pro` refused port `4505`; local `kimi*` refused port `4504`.
- `cf_kimi_k26` is reachable but slow, so it is fallback/chat capacity rather than primary coding capacity.

Preliminary tier map:

```text
fast_coder = cerebras_gptoss, groq_gptoss, mistral_small, scnet_qwen30b, scnet_ds_flash
primary_coder = github_gpt4o, github_gpt4o_mini, cerebras_gptoss, groq_gptoss
strong_coder = github_gpt4o, github_gpt4o_mini, or_gptoss_120b, scnet_qwen235b, scnet_ds_flash, scnet_ds_pro
fallback_coder = mistral_small, mistral_pixtral, mistral_large, mistral_devstral, github_codestral, cf_kimi_k26
```
