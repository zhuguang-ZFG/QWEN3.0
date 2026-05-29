from context_pipeline import RequestContext
from context_pipeline.pipeline import Pipeline
from context_pipeline.processors import (
    ide_detection_processor,
    scenario_classification_processor,
    code_context_processor,
    prompt_composition_processor,
    cache_optimization_processor,
)
from context_pipeline.factory import build_default_pipeline


def test_pipeline_runs_processors_in_order():
    log = []

    def proc_a(ctx):
        log.append("a")
        return ctx

    def proc_b(ctx):
        log.append("b")
        return ctx

    pipe = Pipeline().add("a", proc_a).add("b", proc_b)
    ctx = pipe.process(RequestContext())

    assert log == ["a", "b"]
    assert ctx.processors_applied == ["a", "b"]


def test_pipeline_stages_property():
    pipe = Pipeline().add("x", lambda c: c).add("y", lambda c: c)
    assert pipe.stages == ["x", "y"]


def test_ide_detection_from_user_agent():
    ctx = RequestContext(
        headers={"user-agent": "cursor/1.0"},
        messages=[{"role": "user", "content": "hello"}],
    )
    ctx = ide_detection_processor(ctx)
    assert ctx.ide == "cursor"


def test_ide_detection_from_system_prompt():
    ctx = RequestContext(
        headers={},
        messages=[{"role": "system", "content": "You are Kiro, an AI IDE"}],
    )
    ctx = ide_detection_processor(ctx)
    assert ctx.ide == "kiro"


def test_ide_detection_no_ide():
    ctx = RequestContext(
        headers={"user-agent": "python-requests/2.28"},
        messages=[{"role": "user", "content": "hello"}],
    )
    ctx = ide_detection_processor(ctx)
    assert ctx.ide == ""


def test_scenario_classification_coding_when_ide_present():
    ctx = RequestContext(ide="cursor")
    ctx = scenario_classification_processor(ctx)
    assert ctx.scenario == "coding"


def test_scenario_classification_chat_when_no_ide():
    ctx = RequestContext(ide="")
    ctx = scenario_classification_processor(ctx)
    assert ctx.scenario == "chat"


def test_scenario_classification_vision_when_image_present():
    ctx = RequestContext(
        ide="cursor",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": "what is this?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ]}],
    )
    ctx = scenario_classification_processor(ctx)
    assert ctx.scenario == "vision"


def test_prompt_composition_processor_builds_structured_prompt():
    ctx = RequestContext(ide="Cursor", scenario="coding", code_context="server.py | embeddings")
    ctx = prompt_composition_processor(ctx)
    assert "编程助手" in ctx.system_prompt
    assert "Cursor" in ctx.system_prompt
    assert "编码实现" in ctx.system_prompt
    assert "server.py" in ctx.system_prompt
    assert "质量门控" in ctx.system_prompt


def test_cache_optimization_puts_stable_content_first():
    ctx = RequestContext(
        system_prompt="[角色] 编程助手\n\n[上下文]\nserver.py | embeddings\n\n[质量门控] linter"
    )
    ctx = cache_optimization_processor(ctx)
    parts = ctx.system_prompt.split("\n\n")
    context_idx = next(i for i, p in enumerate(parts) if p.startswith("[上下文]"))
    stable_idx = next(i for i, p in enumerate(parts) if "角色" in p)
    assert stable_idx < context_idx


def test_code_context_processor_uses_unified_retrieval_text(monkeypatch):
    monkeypatch.setenv("LIMA_CONTEXT_PREFLIGHT", "1")
    ctx = RequestContext(
        scenario="coding",
        messages=[{"role": "user", "content": "fix routing_engine.py health bug"}],
    )

    monkeypatch.setattr(
        "context_pipeline.retrieval_injection.build_retrieval_text",
        lambda _messages: "[代码上下文]\n[routing_engine.py]",
    )

    ctx = code_context_processor(ctx)

    assert "[代码上下文]" in ctx.code_context
    assert "routing_engine.py" in ctx.code_context


def test_default_pipeline_processes_full_request():
    pipe = build_default_pipeline()
    ctx = RequestContext(
        headers={"user-agent": "cursor/1.0"},
        messages=[{"role": "user", "content": "fix the bug in server.py"}],
        path="/v1/chat/completions",
    )
    ctx = pipe.process(ctx)

    assert ctx.ide == "cursor"
    assert ctx.scenario == "coding"
    assert "编程助手" in ctx.system_prompt
    assert "编码实现" in ctx.system_prompt
    assert "质量门控" in ctx.system_prompt
    assert len(ctx.processors_applied) == 5
    assert ctx.processors_applied == [
        "ide_detection",
        "scenario_classification",
        "code_context",
        "prompt_composition",
        "cache_optimization",
    ]


def test_default_pipeline_chat_scenario():
    pipe = build_default_pipeline()
    ctx = RequestContext(
        headers={"user-agent": "python-requests/2.28"},
        messages=[{"role": "user", "content": "what is FastAPI?"}],
        path="/v1/chat/completions",
    )
    ctx = pipe.process(ctx)

    assert ctx.ide == ""
    assert ctx.scenario == "chat"
    assert "联网能力" in ctx.system_prompt
    assert "技术问答" in ctx.system_prompt
