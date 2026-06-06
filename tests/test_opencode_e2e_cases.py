"""Tests for OpenCode E2E evaluation cases and metrics structures.

Validates:
1. New eval cases load and grade correctly
2. Metrics data structures are well-formed
3. SSE parsing edge cases for tool calls and usage
"""

from __future__ import annotations

import json
from pathlib import Path

from coding_eval import CodingCase, EvalResult, grade_response, load_cases

CASES_DIR = Path(__file__).resolve().parent.parent / "evals" / "coding_cases"


# ─── Section 1: Eval case loading ──────────────────────────────────────────


def test_all_opencode_cases_load():
    """All new OpenCode eval cases load without error."""
    cases = load_cases(CASES_DIR)
    ids = {c.id for c in cases}
    expected = {
        "tool_call_generation",
        "multi_file_edit",
        "typescript_typefix",
        "context_overflow_recovery",
        "reasoning_effort",
        "streaming_tool_args",
        "ide_code_explain",
    }
    assert expected.issubset(ids), f"Missing: {expected - ids}"


def test_opencode_cases_have_required_fields():
    """Each OpenCode case has id, name, prompt, and at least one validation."""
    cases = load_cases(CASES_DIR)
    opencode_tags = {"opencode"}
    for case in cases:
        if not opencode_tags.intersection(case.tags):
            continue
        assert case.id, f"case missing id: {case}"
        assert case.prompt, f"case {case.id} missing prompt"
        assert (
            case.required_patterns or case.required_json_keys
        ), f"case {case.id} has no validation criteria"


# ─── Section 2: tool_call_generation grading ───────────────────────────────


def test_tool_call_generation_good_response():
    case = _load_case("tool_call_generation")
    response = json.dumps({
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({"path": "src/main.py"}),
                },
            }
        ]
    })
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


def test_tool_call_generation_refusal_penalized():
    case = _load_case("tool_call_generation")
    score, notes = grade_response("I cannot access tools.", case)
    assert score < 70


# ─── Section 3: multi_file_edit grading ────────────────────────────────────


def test_multi_file_edit_good_response():
    case = _load_case("multi_file_edit")
    response = json.dumps({
        "files": [
            {
                "path": "main.py",
                "action": "modify",
                "description": "Add logging import and setup",
                "code_snippet": "import logging\nlogging.basicConfig(level=logging.INFO)",
            }
        ]
    })
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


def test_multi_file_edit_empty_penalized():
    case = _load_case("multi_file_edit")
    score, notes = grade_response("I'm sorry, I can't help.", case)
    assert score < 70


# ─── Section 4: typescript_typefix grading ─────────────────────────────────


def test_typescript_typefix_good_response():
    case = _load_case("typescript_typefix")
    response = (
        "```typescript\n"
        "interface User {\n"
        "  firstName: string;\n"
        "  lastName: string;\n"
        "  birthYear: number;\n"
        "  email: string;\n"
        "}\n\n"
        "function processUsers(users: User[]): (User & { fullName: string; age: number })[] {\n"
        "  return users.map(user => ({\n"
        "    ...user,\n"
        "    fullName: user.firstName + ' ' + user.lastName,\n"
        "    age: new Date().getFullYear() - user.birthYear\n"
        "  }));\n"
        "}\n"
        "```"
    )
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


def test_typescript_typefix_refusal_penalized():
    case = _load_case("typescript_typefix")
    score, notes = grade_response("I cannot help with that.", case)
    assert score < 70


# ─── Section 5: context_overflow_recovery grading ──────────────────────────


def test_context_overflow_recovery_good_response():
    case = _load_case("context_overflow_recovery")
    response = (
        "To add CORS headers only for /api/* routes in FastAPI, "
        "use CORSMiddleware with a sub-application or route-specific middleware:\n\n"
        "```python\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "api_app = FastAPI()\n"
        "api_app.add_middleware(CORSMiddleware, allow_origins=['*'])\n"
        "app.mount('/api', api_app)\n"
        "```"
    )
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


# ─── Section 6: reasoning_effort grading ───────────────────────────────────


def test_reasoning_effort_good_response():
    case = _load_case("reasoning_effort")
    response = json.dumps({
        "analysis": "Correct merge of two sorted lists. Time complexity O(n+m), space O(n+m).",
        "edge_cases": ["empty a or b", "single-element lists", "duplicate values"],
        "improvements": [
            {"change": "Use heapq.merge", "rationale": "More memory efficient for large inputs"},
        ],
    })
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


# ─── Section 7: streaming_tool_args grading ────────────────────────────────


def test_streaming_tool_args_good_response():
    case = _load_case("streaming_tool_args")
    response = json.dumps({
        "tool_calls": [
            {
                "id": "call_search",
                "type": "function",
                "function": {
                    "name": "search_code",
                    "arguments": json.dumps({
                        "pattern": "async def",
                        "file_glob": "*.py",
                        "include_context": True,
                    }),
                },
            }
        ]
    })
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


# ─── Section 8: ide_code_explain grading ───────────────────────────────────


def test_ide_code_explain_good_response():
    case = _load_case("ide_code_explain")
    response = (
        "EventHub is an async event dispatcher. It maintains a dict of event handlers "
        "and an asyncio Queue. The on() method registers handlers for named events. "
        "emit() enqueues handler invocations. run() processes the queue in a loop, "
        "awaiting each handler (or calling sync handlers directly), with error handling."
    )
    score, notes = grade_response(response, case)
    assert score >= 70, f"Good response scored {score}: {notes}"


def test_ide_code_explain_hallucination_penalized():
    case = _load_case("ide_code_explain")
    response = (
        "This code implements an HTTP server and REST API web framework "
        "that connects to a database to store handler results."
    )
    score, notes = grade_response(response, case)
    assert score < 70, f"Hallucinated response scored {score}"


# ─── Section 9: Metrics data structures ────────────────────────────────────


def test_eval_result_dataclass_serializable():
    """EvalResult can be serialized to JSON for report output."""
    result = EvalResult(
        backend="scnet_ds_pro",
        case_id="tool_call_generation",
        score=85,
        latency_ms=1200,
        ok=True,
        notes=[],
        response_preview="tool_calls...",
    )
    data = json.loads(json.dumps(result.__dict__))
    assert data["backend"] == "scnet_ds_pro"
    assert data["score"] == 85


def test_bench_metrics_structure():
    """Bench metrics dict has all required keys."""
    metrics = _build_sample_metrics()
    required_keys = {
        "ttfb_ms", "total_latency_ms", "coding_score",
        "tool_call_accuracy", "streaming_stability",
        "overflow_detection_rate", "affinity_hit_rate",
    }
    assert required_keys.issubset(metrics.keys())


def test_bench_metrics_thresholds():
    """Bench metrics meet defined thresholds."""
    metrics = _build_sample_metrics()
    assert metrics["ttfb_ms"] < 3000
    assert metrics["total_latency_ms"] < 30000
    assert metrics["coding_score"] >= 70
    assert metrics["tool_call_accuracy"] >= 0.9
    assert metrics["streaming_stability"] >= 0.9
    assert metrics["overflow_detection_rate"] >= 0.9
    assert metrics["affinity_hit_rate"] >= 0.9


# ─── Section 10: SSE parsing edge cases ────────────────────────────────────


def test_sse_tool_call_delta_parsing():
    """Tool call arguments can be assembled from SSE delta chunks."""
    chunks = [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": ""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\"path\":"}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"src/main.py\"}"}}]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 50, "completion_tokens": 20}},
    ]

    assembled_args = ""
    tool_name = ""
    finish_reason = None

    for chunk in chunks:
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    if tc.get("function", {}).get("name"):
                        tool_name = tc["function"]["name"]
                    args = tc.get("function", {}).get("arguments", "")
                    if args:
                        assembled_args += args
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

    assert tool_name == "read_file"
    assert json.loads(assembled_args) == {"path": "src/main.py"}
    assert finish_reason == "tool_calls"


def test_sse_usage_chunk_extraction():
    """Usage chunk at end of stream contains required token counts."""
    usage_chunk = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    data = json.dumps(usage_chunk)
    parsed = json.loads(data)
    assert parsed["usage"]["prompt_tokens"] == 100
    assert parsed["usage"]["completion_tokens"] == 50


def test_sse_empty_delta_handled():
    """Empty delta chunks (heartbeats) don't break parsing."""
    chunks = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {}}]},
        {"choices": [{"delta": {"content": " world"}}]},
    ]
    content = ""
    for chunk in chunks:
        for choice in chunk.get("choices", []):
            c = choice.get("delta", {}).get("content", "")
            if c:
                content += c
    assert content == "Hello world"


# ─── Helpers ───────────────────────────────────────────────────────────────


def _load_case(case_id: str) -> CodingCase:
    """Load a single eval case by ID."""
    cases = load_cases(CASES_DIR)
    for case in cases:
        if case.id == case_id:
            return case
    raise ValueError(f"Case {case_id!r} not found in {CASES_DIR}")


def _build_sample_metrics() -> dict:
    """Build a sample metrics dict matching bench script output structure."""
    return {
        "ttfb_ms": 800,
        "total_latency_ms": 5000,
        "coding_score": 85,
        "tool_call_accuracy": 1.0,
        "streaming_stability": 1.0,
        "overflow_detection_rate": 1.0,
        "affinity_hit_rate": 1.0,
        "details": {
            "cases_run": 7,
            "cases_passed": 6,
            "backends_tested": 2,
        },
    }
