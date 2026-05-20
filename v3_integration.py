"""
LiMa V3 Integration — server.py 调用的统一入口
把 router_v3 + health_tracker + sticky_session 组合成一个简单接口。

用法:
    from v3_integration import handle_request_v3
    result = await handle_request_v3(query, messages, fmt, ide_source, ...)
"""

import time
import json
import asyncio
from typing import Optional

import router_v3
import health_tracker
import sticky_session


async def handle_request_v3(
    query: str,
    messages: list,
    fmt: str = "openai",
    ide_source: str = "",
    model: str = "",
    max_tokens: int = 4096,
    call_backend_fn=None,
) -> dict:
    """V3 路由统一入口。返回 {"answer": str, "backend": str, "ms": int}"""
    t0 = time.time()

    # Layer 1: 分类
    req_type = "ide" if (fmt == "anthropic" or ide_source in router_v3.IDE_SOURCES) else "chat"

    # Sticky Session: 检查是否有已绑定的后端
    messages_json = json.dumps(messages, ensure_ascii=False)
    sticky_key = sticky_session.compute_key(model or "default", messages_json)
    pinned = sticky_session.get_pinned_backend(sticky_key)

    # Layer 2: 选择后端
    hmap = health_tracker.get_health_map()
    backends = router_v3.select_backends(req_type, hmap)

    # 如果有 sticky 绑定且后端健康，优先使用
    if pinned and hmap.get(pinned, "healthy") != "dead":
        if pinned not in backends:
            backends.insert(0, pinned)
        else:
            backends.remove(pinned)
            backends.insert(0, pinned)

    # Layer 3: 执行（按顺序尝试，最多 MAX_FALLBACKS 个）
    if not call_backend_fn:
        return {"answer": "", "backend": "none", "ms": 0}

    last_error = None
    for backend in backends[:router_v3.MAX_FALLBACKS]:
        if health_tracker.is_cooled_down(backend):
            continue
        try:
            result = await asyncio.wait_for(
                call_backend_fn(backend, messages, max_tokens),
                timeout=15.0
            )
            if result and len(result.strip()) > 5:
                ms = int((time.time() - t0) * 1000)
                health_tracker.record_success(backend, ms)
                sticky_session.pin_backend(sticky_key, backend)
                return {"answer": result, "backend": backend, "ms": ms}
            else:
                health_tracker.record_failure(backend, error_code=None)
        except asyncio.TimeoutError:
            health_tracker.record_failure(backend, error_code=408)
            last_error = "timeout"
        except Exception as e:
            code = getattr(e, "status_code", None) or _extract_code(e)
            health_tracker.record_failure(backend, error_code=code)
            last_error = str(e)

    # 全部失败: 检测批量熔断
    if health_tracker.detect_and_reset_mass_failure():
        # 重置后重试一次直连后端
        for b in router_v3.DIRECT_BACKENDS[:2]:
            try:
                result = await asyncio.wait_for(
                    call_backend_fn(b, messages, max_tokens), timeout=15.0
                )
                if result and len(result.strip()) > 5:
                    ms = int((time.time() - t0) * 1000)
                    return {"answer": result, "backend": b, "ms": ms}
            except Exception:
                pass

    ms = int((time.time() - t0) * 1000)
    return {"answer": "", "backend": "exhausted", "ms": ms, "error": last_error}


def _extract_code(e: Exception) -> Optional[int]:
    """从异常中提取 HTTP 状态码"""
    for attr in ("status_code", "code", "status"):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            return val
    s = str(e)
    if "429" in s:
        return 429
    if "401" in s:
        return 401
    if "403" in s:
        return 403
    return None
