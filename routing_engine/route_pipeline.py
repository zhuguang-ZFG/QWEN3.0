"""内部辅助：classify+recall 与 backends 选择两段，从 __init__.py 拆出以控制行数。

依赖（classify/select/try_recall_backend/trace_span 等）在函数体内通过
``import routing_engine`` 延迟查找，使测试 ``monkeypatch.setattr(routing_engine, ...)``
依然生效（与拆分前行为一致）。
"""

from __future__ import annotations


def _classify_and_recall(
    query: str,
    messages: list[dict],
    fmt: str,
    ide_source: str,
    system_prompt: str,
    headers: dict,
) -> tuple[str, str, str | None, str]:
    """Classify request type/scenario and recall backend + retrieval context."""
    import routing_engine  # 延迟导入，确保 monkeypatch 可替换

    with routing_engine.trace_span("classify") as span:
        req_type = routing_engine.classify(
            query, messages, fmt=fmt, ide_source=ide_source, system_prompt=system_prompt, headers=headers
        )
        if span is not None:
            span.metadata["request_type"] = req_type

    # AUDIT-8-P9: v3.0 起编码能力退役，classify_scenario 永远返回 chat；
    # retrieval 也是 no-op。直接硬编码，避免热路径上的 dataclass 校验与函数调用开销。
    scenario = "chat"
    with routing_engine.trace_span("scenario") as span:
        if span is not None:
            span.metadata["scenario"] = scenario

    with routing_engine.trace_span("recall") as span:
        recall_attempt = routing_engine.try_recall_backend(messages, scenario)
        if span is not None:
            span.metadata["recalled_backend"] = recall_attempt

    retrieval_text = ""
    with routing_engine.trace_span("retrieval") as span:
        if span is not None:
            span.metadata["has_context"] = False

    return req_type, scenario, recall_attempt, retrieval_text


def _select_backends(
    req_type: str,
    scenario: str,
    recall_attempt: str | None,
    messages: list[dict],
    needs_tools: bool,
    preferred_backend: str,
    model: str,
) -> tuple[str, list[str]]:
    """Select backends based on health, sticky session, and recall."""
    import routing_engine  # 延迟导入，确保 monkeypatch 可替换

    with routing_engine.trace_span("select") as span:
        sticky_key = routing_engine.sticky_session.compute_key(model or "default", messages)
        hmap = routing_engine.health_tracker.get_health_map()
        backends = routing_engine.select(
            req_type,
            hmap,
            sticky_key=sticky_key,
            scenario=scenario,
            needs_tools=needs_tools,
            recalled_backend=recall_attempt,
            preferred_backend=preferred_backend or "",
        )
        if span is not None:
            span.metadata["backends"] = backends
        return sticky_key, backends
