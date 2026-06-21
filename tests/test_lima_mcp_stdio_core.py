"""Behavioral tests for lima_mcp_stdio (workspace, jobs, MCP JSON-RPC)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from lima_mcp_stdio.job_runner import job_status, start_async_run
from lima_mcp_stdio.lima_code_query_mcp import handle_request
from lima_mcp_stdio.workspace import resolve_workspace


def test_resolve_workspace_uses_explicit_path(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    assert resolve_workspace(str(project)) == project.resolve()


def test_resolve_workspace_rejects_path_outside_cwd(tmp_path, monkeypatch):
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    monkeypatch.chdir(project)
    with pytest.raises(ValueError, match="must be inside"):
        resolve_workspace(str(outside))


def test_resolve_workspace_honors_env(tmp_path, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("MIMO_MCP_WORKSPACE", str(workspace))
    assert resolve_workspace(None) == workspace.resolve()


def test_start_async_run_rejects_empty_task(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    result = start_async_run(task="   ", workspace=str(ws))
    assert result["ok"] is False
    assert "task is required" in result["error"]


def test_job_status_idle_when_no_jobs(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    result = job_status(workspace=str(ws))
    assert result["ok"] is True
    assert result["status"] == "idle"


def test_job_status_missing_job_returns_error(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    result = job_status(job_id="does-not-exist", workspace=str(ws))
    assert result["ok"] is False
    assert "job not found" in result["error"]


@patch("lima_mcp_stdio.job_runner._spawn_worker", return_value={})
def test_start_async_run_queues_job(mock_spawn, tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    result = start_async_run(task="review routing_engine.py", mode="review", workspace=str(ws))
    assert result["ok"] is True
    assert result["status"] == "running"
    assert len(result["job_id"]) == 12
    mock_spawn.assert_called_once()

    status = job_status(job_id=result["job_id"], workspace=str(ws))
    assert status["job_id"] == result["job_id"]
    assert status["status"] in {"queued", "running", "done", "failed"}


def test_handle_request_tools_list():
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response["id"] == 1
    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert tool_names == {"search_code", "get_module_context", "find_related", "trace_symbol"}


def test_handle_request_initialize():
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    assert response["result"]["serverInfo"]["name"] == "lima-code-query"


def test_handle_request_unknown_method():
    response = handle_request({"jsonrpc": "2.0", "id": 3, "method": "nope/method"})
    assert response["error"]["code"] == -32601


def test_handle_request_tools_call_search_code():
    mock_query = MagicMock()
    mock_query.search_code.return_value = [{"path": "routing_engine.py", "score": 0.9}]
    with patch("lima_mcp_stdio.lima_code_query_mcp.code_query", mock_query):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "search_code", "arguments": {"query": "routing"}},
            }
        )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload[0]["path"] == "routing_engine.py"
    mock_query.search_code.assert_called_once_with("routing", 8)


def test_handle_request_tools_call_unknown_tool():
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "missing_tool", "arguments": {}},
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert "Unknown tool" in payload["error"]


def test_lima_code_query_get_module_context_real_file():
    from lima_mcp_stdio.lima_code_query_mcp import LimaCodeQuery

    query = LimaCodeQuery()
    ctx = query.get_module_context("routing_selector/core.py")
    assert "error" not in ctx
    assert ctx["path"] == "routing_selector/core.py"
    assert any(fn["name"] == "select" for fn in ctx.get("functions", []))


def test_lima_code_query_get_module_context_missing_file():
    from lima_mcp_stdio.lima_code_query_mcp import LimaCodeQuery

    query = LimaCodeQuery()
    ctx = query.get_module_context("does/not/exist.py")
    assert "error" in ctx
