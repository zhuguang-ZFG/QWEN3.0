from context_pipeline.artifact import (
    ArtifactHandle,
    create_handle,
    should_use_handle,
    render_handles_for_context,
)


def test_create_handle_from_content():
    content = "import os\n" * 50
    handle = create_handle("server.py", content, symbols=["main", "app", "route"])
    assert handle.path == "server.py"
    assert handle.line_count == 51  # 50 newlines + trailing content = 51 lines
    assert handle.size_bytes > 0
    assert "main" in handle.symbols


def test_artifact_handle_to_context_line():
    h = ArtifactHandle(
        path="routing_engine.py",
        size_bytes=5000,
        line_count=150,
        summary="routing logic",
        symbols=["select", "classify", "route", "fallback", "health", "extra"],
    )
    line = h.to_context_line()
    assert "routing_engine.py" in line
    assert "select" in line
    assert "(+1)" in line


def test_should_use_handle_large_file():
    large = "x\n" * 300
    assert should_use_handle(large) is True


def test_should_use_handle_small_file():
    small = "x\n" * 10
    assert should_use_handle(small) is False


def test_is_large_property():
    h = ArtifactHandle("big.py", 20000, 500, "big file", [])
    assert h.is_large is True

    h2 = ArtifactHandle("small.py", 100, 10, "small", [])
    assert h2.is_large is False


def test_render_handles_for_context():
    handles = [
        ArtifactHandle("a.py", 5000, 100, "", ["func_a", "class_a"]),
        ArtifactHandle("b.py", 3000, 80, "", ["func_b"]),
        ArtifactHandle("c.py", 2000, 50, "", ["func_c"]),
    ]
    rendered = render_handles_for_context(handles, max_chars=500)
    assert "[Artifact References]" in rendered
    assert "a.py" in rendered
    assert "func_a" in rendered


def test_render_handles_respects_max_chars():
    handles = [
        ArtifactHandle(f"file_{i}.py", 1000, 50, "", [f"sym_{i}"])
        for i in range(100)
    ]
    rendered = render_handles_for_context(handles, max_chars=200)
    assert len(rendered) <= 200
