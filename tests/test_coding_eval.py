import json

from coding_eval import (
    CodingCase,
    EvalResult,
    candidate_backends,
    grade_response,
    load_cases,
    run_eval,
    write_markdown_report,
)


def test_load_cases_reads_json_files(tmp_path):
    case_path = tmp_path / "case.json"
    case_path.write_text(
        json.dumps(
            {
                "id": "sample",
                "name": "Sample",
                "prompt": "Return code",
                "required_patterns": ["def add"],
                "forbidden_patterns": ["I cannot"],
                "min_chars": 10,
            }
        ),
        encoding="utf-8",
    )

    cases = load_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].id == "sample"
    assert cases[0].required_patterns == ["def add"]


def test_grade_response_rewards_required_patterns_and_python_compile():
    case = CodingCase(
        id="bugfix",
        name="Bugfix",
        prompt="Fix it",
        required_patterns=["def add", "return"],
        forbidden_patterns=["I cannot"],
        min_chars=20,
        python_must_compile=True,
    )

    score, notes = grade_response(
        "```python\ndef add(a, b):\n    return a + b\n```", case
    )

    assert score == 100
    assert notes == []


def test_grade_response_penalizes_missing_and_forbidden_patterns():
    case = CodingCase(
        id="bad",
        name="Bad",
        prompt="Fix it",
        required_patterns=["def add"],
        forbidden_patterns=["I cannot"],
        min_chars=20,
    )

    score, notes = grade_response("I cannot help.", case)

    assert score < 100
    assert "missing pattern: def add" in notes
    assert "forbidden pattern: I cannot" in notes


def test_grade_response_can_require_json_object():
    case = CodingCase(
        id="json",
        name="JSON",
        prompt="Return JSON",
        required_json_keys=["action", "files"],
    )

    score, notes = grade_response('{"action":"edit","files":["x.py"]}', case)

    assert score == 100
    assert notes == []


def test_candidate_backends_prefers_code_like_configured_backends():
    backends = {
        "plain": {"key": "k", "model": "chat-model"},
        "qwen_coder": {"key": "k", "model": "qwen-coder"},
        "no_key_coder": {"key": "", "model": "qwen-coder"},
        "free_coder": {"key": "none", "model": "codestral"},
    }

    result = candidate_backends(backends)

    assert result == ["free_coder", "qwen_coder"]


def test_run_eval_uses_supplied_call_fn_and_scores_results():
    cases = [
        CodingCase(
            id="bugfix",
            name="Bugfix",
            prompt="Fix add",
            required_patterns=["def add"],
            min_chars=10,
        )
    ]

    def fake_call(backend, messages, max_tokens):
        assert backend == "coder_a"
        assert messages[-1]["content"] == "Fix add"
        return "def add(a, b):\n    return a + b"

    results = run_eval(cases, ["coder_a"], fake_call)

    assert len(results) == 1
    assert results[0].backend == "coder_a"
    assert results[0].case_id == "bugfix"
    assert results[0].score == 100


def test_run_eval_normalizes_local_socket_permission_errors():
    case = CodingCase(id="review", name="Review", prompt="review", min_chars=1)

    def blocked_call(_backend, _messages, _max_tokens):
        raise OSError("[WinError 10013] local language message")

    results = run_eval([case], ["blocked"], blocked_call)

    assert results[0].score == 0
    assert results[0].notes == [
        "call failed: OSError: WinError 10013: socket access blocked by local OS/firewall policy"
    ]


def test_markdown_report_ranks_by_score_then_latency(tmp_path):
    out = tmp_path / "ranking.md"
    write_markdown_report(
        [
            EvalResult("slow_good", "a", 100, 1000, True, [], "ok"),
            EvalResult("fast_good", "a", 100, 200, True, [], "ok"),
            EvalResult("bad", "a", 40, 50, False, ["json parse failed"], ""),
        ],
        out,
    )

    lines = [
        line for line in out.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `")
    ]
    assert lines[0].startswith("| `fast_good`")
    assert lines[1].startswith("| `slow_good`")
    assert lines[2].startswith("| `bad`")
