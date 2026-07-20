"""隐藏问题审查修复的回归测试。

覆盖 4 视角审查收敛后的 5 个真实问题：
- P0 #1：DashScope 同步阻塞在 async 函数里 → 必须用 to_thread
- P1 #3：Redis 客户端必须设 socket_timeout
- P1 #5：MCP main() 畸形 JSON 不能崩主循环 + handle_request 类型校验
- P2 #4：routes.py 不能有重复定义的 _quota_for / _claim_idempotency_key
"""

from __future__ import annotations


# ── P0 #1：DashScope 同步调用必须包进 to_thread，不能裸跑在事件循环 ──────────


def test_device_draw_handler_generate_image_uses_to_thread():
    """_generate_image 是 async，内部 DashScope 同步调用必须经 asyncio.to_thread。

    静态检查：源码里不能再出现裸 `client.generate(`，必须 `await asyncio.to_thread(...)`。
    """
    import re
    from pathlib import Path

    src = Path("device_gateway/device_draw_handler.py").read_text(encoding="utf-8")
    # 裸 client.generate( 在 async 函数内 = 同步阻塞事件循环
    bare_calls = re.findall(r"^\s*result\s*=\s*client\.generate\(", src, re.MULTILINE)
    assert not bare_calls, (
        "_generate_image 内仍有裸 client.generate() 同步调用，会阻塞事件循环；"
        "应改为 await asyncio.to_thread(client.generate, ...)"
    )


def test_images_backends_dashscope_uses_to_thread():
    """routes/images_backends.py 的 DashScope 调用同样必须经 to_thread。"""
    import re
    from pathlib import Path

    src = Path("routes/images_backends.py").read_text(encoding="utf-8")
    bare_calls = re.findall(r"^\s*result\s*=\s*client\.generate\(", src, re.MULTILINE)
    assert not bare_calls, (
        "images_backends._generate_via_dashscope_i2i 内仍有裸 client.generate()，应改为 await asyncio.to_thread(...)"
    )


# ── P1 #3：Redis 客户端必须设 socket_timeout ────────────────────────────────


def test_redis_client_has_socket_timeout():
    """connect_redis 创建的 Redis 客户端必须设 socket_timeout，避免慢/断无限阻塞。"""
    from pathlib import Path

    src = Path("device_gateway/redis_store_helpers.py").read_text(encoding="utf-8")
    # 粗略检查：from_url 调用必须含 socket_timeout 参数
    assert "socket_timeout" in src, "redis_store_helpers.connect_redis 的 Redis.from_url 必须显式设 socket_timeout"


# ── P1 #5：MCP main() 必须把 handle_request 纳入 try + 类型校验 ───────────────


def test_mcp_main_handles_arbitrary_exception(monkeypatch):
    """stdio 读循环处理畸形 JSON（合法 JSON 但非对象）时不能退出主循环。

    CORE-O5/CORE-Y1(2026-07-20 第二轮审查)后,读循环从 server.main() 抽到
    dlc_mcp.stdio_loop.run_stdio_loop;本测试守护"非对象请求不崩循环"的行为,
    monkeypatch 目标随之改到 stdio_loop 模块。
    """
    import io
    from dlc_mcp import server as mcp_server
    from dlc_mcp import stdio_loop

    # 模拟 stdin 依次输入：非对象 JSON、空行、合法 initialize
    fake_stdin = io.StringIO('["not", "an", "object"]\n\n{"jsonrpc":"2.0","id":1,"method":"initialize"}\n')

    class _BufferedStdout:
        """带 buffer.write() 的最小 stdout stub，行为与真实 sys.stdout 一致。"""

        def __init__(self) -> None:
            self.buffer = io.BytesIO()

    monkeypatch.setattr(stdio_loop.sys, "stdin", fake_stdin)
    monkeypatch.setattr(stdio_loop.sys, "stdout", _BufferedStdout())

    # run_stdio_loop 必须正常跑完，不抛任何异常（旧代码会因为 list.get 崩溃）。
    # 非对象 JSON 走 handle_request 得 -32600，畸形行得 -32700，循环不退出。
    stdio_loop.run_stdio_loop(httpx_client_stub(), mcp_server.handle_request)


def test_mcp_handle_request_rejects_non_dict():
    """handle_request 对非 dict 请求必须返回 -32600 Invalid Request，不抛异常。"""
    from dlc_mcp import server as mcp_server

    for bad_req in (["list"], "string", 42, None):
        resp = mcp_server.handle_request(httpx_client_stub(), bad_req)  # type: ignore[arg-type]
        assert resp.get("error", {}).get("code") == -32600, f"非 dict 请求 {bad_req!r} 应返回 -32600，实际: {resp}"


def test_mcp_tools_call_rejects_non_dict_params():
    """tools/call 的 params 为非对象（list/str）时必须返回 -32602，不抛异常。"""
    from dlc_mcp import server as mcp_server

    for bad_params in ([], "x", 1):
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": bad_params}
        resp = mcp_server.handle_request(httpx_client_stub(), req)
        assert resp.get("error", {}).get("code") == -32602, f"params={bad_params!r} 应返回 -32602，实际: {resp}"


def test_mcp_tools_call_rejects_non_dict_arguments():
    """tools/call 的 arguments 为非对象（str/list）时必须返回 -32602，不抛异常。"""
    from dlc_mcp import server as mcp_server

    for bad_args in ("x", [], 1):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "dlc.write_text", "arguments": bad_args},
        }
        resp = mcp_server.handle_request(httpx_client_stub(), req)
        assert resp.get("error", {}).get("code") == -32602, f"arguments={bad_args!r} 应返回 -32602，实际: {resp}"


# ── P2 #4：routes.py 不能有重复定义 ─────────────────────────────────────────


def test_routes_no_duplicate_definitions():
    """_quota_for 和 _claim_idempotency_key 各只能定义一次。"""
    import re
    from pathlib import Path

    src = Path("dlc_api/routes.py").read_text(encoding="utf-8")
    quota_defs = re.findall(r"^def _quota_for\(", src, re.MULTILINE)
    # routes.py 里 _quota_for 恰好定义一次（防重复定义回归）。
    assert len(quota_defs) == 1, f"_quota_for 定义了 {len(quota_defs)} 次，应只有 1 次"
    # 幂等键逻辑已抽到 dlc_api/idempotency.py（routes.py 用 import 别名，不重复定义）。
    assert not re.findall(r"^def _claim_idempotency_key\(", src, re.MULTILINE), (
        "_claim_idempotency_key 不应在 routes.py 重复定义，应从 dlc_api.idempotency import"
    )
    idem_src = Path("dlc_api/idempotency.py").read_text(encoding="utf-8")
    claim_defs = re.findall(r"^def claim_idempotency_key\(", idem_src, re.MULTILINE)
    release_defs = re.findall(r"^def release_idempotency_key\(", idem_src, re.MULTILINE)
    assert len(claim_defs) == 1, f"claim_idempotency_key 定义了 {len(claim_defs)} 次，应只有 1 次"
    assert len(release_defs) == 1, f"release_idempotency_key 定义了 {len(release_defs)} 次，应只有 1 次"


# ── 辅助 ───────────────────────────────────────────────────────────────────


def httpx_client_stub():
    """一个最小 httpx.Client，用于不真正发请求的 handle_request 测试。"""
    import httpx

    return httpx.Client()
