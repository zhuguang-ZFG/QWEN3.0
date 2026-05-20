"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现
"""

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import router_v3
import health_tracker
import sticky_session
import skills_injector as skills_mod
import semantic_cache
from response_builder import build_response, build_anthropic_response, make_chat_id

MAX_FALLBACKS = 5


@dataclass
class RouteResult:
    backend: str = ""
    answer: str = ""
    request_type: str = "chat"
    ms: int = 0
    fallback_used: bool = False
    skills_injected: list = field(default_factory=list)


# ─── Layer 1: 分类 ───────────────────────────────────────────────────────────

def classify(query: str, messages: list[dict], *,
             fmt: str = "openai", ide_source: str = "",
             system_prompt: str = "", headers: dict = None) -> str:
    """判断请求类型: ide / chat / vision / image"""
    headers = headers or {}

    if fmt == "anthropic":
        return "ide"

    if ide_source and ide_source in router_v3.IDE_SOURCES:
        return "ide"

    ua = headers.get("user-agent", "").lower()
    if any(x in ua for x in ["claude-code", "cursor", "aider", "codex", "cline"]):
        return "ide"

    if system_prompt and router_v3.detect_ide_from_system_prompt(system_prompt):
        return "ide"

    if _has_image_blocks(messages):
        return "vision"

    return "chat"


def _has_image_blocks(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content", []) if isinstance(m, dict) else []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False


# ─── Layer 2: 选择 ───────────────────────────────────────────────────────────

def select(request_type: str, health_map: dict,
           sticky_key: str = None) -> list[str]:
    """从对应池选健康后端，sticky 优先"""
    result = router_v3.select_backends(request_type, health_map)

    if sticky_key:
        pinned = sticky_session.get_pinned_backend(sticky_key)
        if pinned and health_map.get(pinned, "healthy") != "dead":
            result = _prioritize(pinned, result)

    return result[:MAX_FALLBACKS]


def _prioritize(pinned: str, backends: list[str]) -> list[str]:
    """将 pinned 后端排到第一，返回新列表"""
    others = [b for b in backends if b != pinned]
    return [pinned] + others


# ─── Layer 3: Skills 注入 ────────────────────────────────────────────────────

def inject_skills(messages: list[dict], *,
                  backend: str = "", ide_source: str = "",
                  system_prompt: str = "") -> list[dict]:
    """根据后端能力和 IDE 注入 skills"""
    return skills_mod.apply_skills(
        backend=backend, messages=messages,
        system_prompt=system_prompt, ide_source=ide_source)


# ─── Layer 4: 执行 ───────────────────────────────────────────────────────────

def execute(backends: list[str],
            call_fn: Callable[[str, list[dict], int], str],
            messages: list[dict],
            max_tokens: int = 4096) -> tuple[str, str, int]:
    """按序尝试后端，失败则 fallback。返回 (backend, answer, error_count)"""
    t0 = time.time()
    errors = 0

    for backend in backends[:MAX_FALLBACKS]:
        if health_tracker.is_cooled_down(backend):
            errors += 1
            continue
        try:
            answer = call_fn(backend, messages, max_tokens)
            if answer and len(answer.strip()) > 5:
                latency_ms = (time.time() - t0) * 1000
                health_tracker.record_success(backend, latency_ms)
                return backend, answer, errors
            else:
                health_tracker.record_failure(backend, error_code=None)
                errors += 1
        except Exception as e:
            code = _extract_code(e)
            health_tracker.record_failure(backend, error_code=code)
            errors += 1

    # 批量熔断检测 + 直连保底
    if health_tracker.detect_and_reset_mass_failure():
        for b in router_v3.DIRECT_BACKENDS[:2]:
            if health_tracker.is_cooled_down(b):
                continue
            try:
                answer = call_fn(b, messages, max_tokens)
                if answer and len(answer.strip()) > 5:
                    return b, answer, errors
            except Exception as e:
                health_tracker.record_failure(b, error_code=_extract_code(e))
                errors += 1

    return "exhausted", "", errors


def _extract_code(e: Exception) -> Optional[int]:
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


# ─── Layer 5: 响应 ───────────────────────────────────────────────────────────

def respond(result: RouteResult, fmt: str = "openai",
            model: str = "lima-1.3") -> dict:
    chat_id = make_chat_id()
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, result.answer, result.backend, model)
    resp = build_response(chat_id, result.answer, result.backend, result.ms)
    resp["x_lima_meta"]["request_type"] = result.request_type
    resp["x_lima_meta"]["skills_injected"] = result.skills_injected
    return resp


# ─── 主入口 ─────────────────────────────────────────────────────────────────

def route(query: str, messages: list[dict], *,
          fmt: str = "openai", ide_source: str = "",
          model: str = "", max_tokens: int = 4096,
          system_prompt: str = "", headers: dict = None,
          call_fn: Callable = None,
          cache_enabled: bool = True) -> RouteResult:
    """统一路由入口。call_fn(backend, messages, max_tokens) -> str"""
    t0 = time.time()

    # 缓存检查 (仅 temperature=0 的确定性请求)
    if cache_enabled:
        cached = semantic_cache.get(model or "default", messages)
        if cached:
            ms = int((time.time() - t0) * 1000)
            return RouteResult(backend="cache", answer=cached,
                               request_type="cache_hit", ms=ms)

    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source,
                        system_prompt=system_prompt, headers=headers)

    sticky_key = sticky_session.compute_key(
        model or "default",
        json.dumps(messages, ensure_ascii=False))

    hmap = health_tracker.get_health_map()
    backends = select(req_type, hmap, sticky_key=sticky_key)

    messages_injected = inject_skills(
        messages, backend=backends[0] if backends else "",
        ide_source=ide_source, system_prompt=system_prompt)

    injected_ids = _get_injected_ids(messages, messages_injected)

    if call_fn:
        final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens)
        if final_backend != "exhausted":
            sticky_session.pin_backend(sticky_key, final_backend)
            if cache_enabled and answer:
                semantic_cache.put(model or "default", messages, 0, answer)
    else:
        final_backend, answer = backends[0] if backends else "none", ""

    ms = int((time.time() - t0) * 1000)
    return RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, ms=ms,
        fallback_used=(final_backend not in ("exhausted", "none") and final_backend != backends[0]),
        skills_injected=injected_ids,
    )


def _get_injected_ids(original: list[dict], modified: list[dict]) -> list[str]:
    """提取被注入的 skill ID"""
    if len(modified) <= len(original):
        return []
    for msg in modified:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if "Available skills:" in content:
                names = content.replace("Available skills:", "").strip()
                return ["dir:" + n.strip() for n in names.split(",") if n.strip()]
    extra = len(modified) - len(original)
    return [f"injected_{extra}_skills"] if extra > 0 else []
