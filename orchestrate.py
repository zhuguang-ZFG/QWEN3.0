"""orchestrate.py — 1+N >> N 编排器
复杂任务拆解为子任务，每个子任务路由到最强专业模型，合并结果。
Superpower 原则：编排层让多个模型协作产生超越单模型的效果。
"""
import sys, os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smart_router

# ── 配置 ────────────────────────────────────────────────────────────────────
MAX_CONCURRENT = 3          # 最大并发子任务数
DECOMPOSE_MAX_TOKENS = 512  # 拆解任务的 token 上限
SYNTHESIZE_MAX_TOKENS = 1024  # 合并结果的 token 上限
COMPLEXITY_THRESHOLD = 0.75   # 复杂度阈值，超过则触发编排

# 多领域关键词（跨领域时触发编排）
MULTI_DOMAIN_KEYWORDS = {
    "hardware": ["电路", "PCB", "硬件", "传感器", "驱动", "GPIO", "ADC"],
    "software": ["代码", "程序", "算法", "编程", "函数", "API", "软件"],
    "mechanical": ["机械", "加工", "刀具", "主轴", "进给", "G代码", "工艺"],
    "theory": ["原理", "理论", "公式", "计算", "分析", "推导", "数学"],
}

# 多步骤指示词
MULTI_STEP_INDICATORS = [
    "首先", "然后", "接着", "最后", "第一步", "第二步",
    "分别", "同时", "以及", "并且", "还需要",
    "对比", "比较", "区别", "优缺点",
    "从.*到.*", "既.*又.*",
]


# ── 核心函数 ─────────────────────────────────────────────────────────────────
def needs_orchestration(query: str, intent: dict) -> bool:
    """判断是否需要编排模式。
    条件：complexity >= 阈值 且 跨多领域，或包含多步骤指示词。

    Args:
        query: 用户原始查询
        intent: smart_router.analyze() 返回的意图字典

    Returns:
        True 表示需要编排，False 表示直接路由
    """
    import re

    complexity = intent.get("complexity", 0.5)

    # 条件1：复杂度高
    if complexity < COMPLEXITY_THRESHOLD:
        return False

    # 条件2：跨多领域
    domains_hit = 0
    for domain, keywords in MULTI_DOMAIN_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            domains_hit += 1
    if domains_hit >= 2:
        return True

    # 条件3：多步骤指示词
    step_count = sum(1 for ind in MULTI_STEP_INDICATORS if re.search(ind, query))
    if step_count >= 2:
        return True

    # 条件4：查询过长（通常意味着复杂问题）
    if len(query) > 300 and complexity >= 0.8:
        return True

    return False


def decompose(query: str) -> list[dict]:
    """将复杂问题拆解为子任务列表。
    调用本地模型，输出 JSON 格式子任务。

    Args:
        query: 用户原始查询

    Returns:
        子任务列表，每个子任务为 dict: {"task": str, "domain": str, "backend_hint": str}
    """
    prompt = (
        "你是一个任务拆解专家。将以下复杂问题拆解为2-4个独立子任务。\n"
        "每个子任务应该可以独立回答，合并后能完整解决原问题。\n\n"
        f"问题：{query[:800]}\n\n"
        "输出 JSON 数组，每个元素包含：\n"
        '- "task": 子任务描述（具体、可独立回答）\n'
        '- "domain": 领域（hardware/software/mechanical/theory/general）\n'
        '- "backend_hint": 建议后端（留空则自动路由）\n\n'
        "只输出 JSON，不要其他文字。"
    )
    resp = smart_router.call_local(
        [{"role": "user", "content": prompt}],
        mt=DECOMPOSE_MAX_TOKENS, t=0.3
    )

    # 解析 JSON
    try:
        # 尝试从响应中提取 JSON 数组
        text = resp.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            subtasks = json.loads(text[start:end])
            # 验证格式
            valid = []
            for st in subtasks[:4]:  # 最多4个子任务
                if isinstance(st, dict) and "task" in st:
                    valid.append({
                        "task": st["task"],
                        "domain": st.get("domain", "general"),
                        "backend_hint": st.get("backend_hint", "")
                    })
            if valid:
                return valid
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # 解析失败：回退为单任务
    return [{"task": query, "domain": "general", "backend_hint": ""}]


def execute_subtasks(subtasks: list[dict]) -> list[dict]:
    """并发执行子任务（ThreadPoolExecutor，最多 MAX_CONCURRENT 个并发）。
    每个子任务调用 smart_router.call_api 或 smart_router.route。

    Args:
        subtasks: decompose() 返回的子任务列表

    Returns:
        结果列表，每个为 dict: {"task": str, "answer": str, "backend": str, "ms": int}
    """
    results = [None] * len(subtasks)

    def _exec_one(idx: int, subtask: dict) -> dict:
        t0 = time.time()
        task_query = subtask["task"]
        hint = subtask.get("backend_hint", "")

        # 如果有后端提示且可用，直接调用
        if hint and hint in smart_router.BACKENDS and smart_router.cb_allow(hint):
            answer = smart_router.call_api(
                hint, [{"role": "user", "content": task_query}]
            )
            if answer and not answer.startswith("[ERR]"):
                return {
                    "task": task_query,
                    "answer": answer,
                    "backend": hint,
                    "ms": int((time.time() - t0) * 1000)
                }

        # 否则走完整路由
        result = smart_router.route(task_query)
        return {
            "task": task_query,
            "answer": result.get("answer", ""),
            "backend": result.get("backend", "unknown"),
            "ms": int((time.time() - t0) * 1000)
        }

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = {
            executor.submit(_exec_one, i, st): i
            for i, st in enumerate(subtasks)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {
                    "task": subtasks[idx]["task"],
                    "answer": f"[子任务执行失败: {e}]",
                    "backend": "error",
                    "ms": 0
                }

    return results


def synthesize(query: str, results: list[dict]) -> str:
    """合并子任务结果为最终回答。
    调用 longcat 或本地模型做合并，产生连贯的综合回答。

    Args:
        query: 用户原始查询
        results: execute_subtasks() 返回的结果列表

    Returns:
        合并后的最终回答字符串
    """
    # 构建合并 prompt
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"【子任务{i}】{r['task']}\n【回答{i}】{r['answer']}")
    combined = "\n\n".join(parts)

    prompt = (
        "你是一个专业的技术文档整合专家。\n"
        "用户提出了一个复杂问题，已被拆解为多个子任务并分别回答。\n"
        "请将以下子任务回答整合为一个连贯、完整、结构清晰的最终回答。\n"
        "要求：去除重复内容，保持逻辑顺序，使用中文。\n\n"
        f"用户原始问题：{query[:500]}\n\n"
        f"子任务回答：\n{combined[:3000]}\n\n"
        "请输出整合后的最终回答："
    )

    # 优先用 longcat，失败则用本地模型
    msgs = [{"role": "user", "content": prompt}]
    answer = smart_router.call_api("longcat_chat", msgs, mt=SYNTHESIZE_MAX_TOKENS)
    if answer and "[ERR]" not in answer and "暂时不可用" not in answer:
        return answer

    # 回退到本地模型
    answer = smart_router.call_local(msgs, mt=SYNTHESIZE_MAX_TOKENS, t=0.5)
    if answer and not answer.startswith("[LOCAL_ERR]"):
        return answer

    # 最终回退：简单拼接
    return "\n\n".join(r["answer"] for r in results if r["answer"])


def orchestrate(query: str) -> dict:
    """编排入口：复杂任务拆解 → 并发执行 → 合并结果。

    流程：
    1. classify_intent → 判断是否需要编排
    2. 需要 → decompose → execute_subtasks → synthesize
    3. 不需要 → 直接 route()

    Args:
        query: 用户原始查询

    Returns:
        与 smart_router.route() 相同格式的 dict:
        {"answer": str, "backend": str, "intent": dict, "total_ms": int, ...}
    """
    t0 = time.time()

    # 意图分析
    intent = smart_router.analyze(query)

    # 再次确认是否需要编排（防止外部直接调用）
    if not needs_orchestration(query, intent):
        return smart_router.route(query)

    # 拆解
    subtasks = decompose(query)

    # 如果拆解失败（只有1个且等于原查询），直接路由
    if len(subtasks) == 1 and subtasks[0]["task"] == query:
        return smart_router.route(query)

    # 并发执行
    results = execute_subtasks(subtasks)

    # 合并
    final_answer = synthesize(query, results)

    # 统计
    backends_used = list(set(r["backend"] for r in results))
    total_ms = int((time.time() - t0) * 1000)
    subtask_ms = [r["ms"] for r in results]

    return {
        "answer": final_answer,
        "backend": f"orchestrate({','.join(backends_used)})",
        "intent": intent,
        "total_ms": total_ms,
        "orchestration": {
            "subtask_count": len(subtasks),
            "backends_used": backends_used,
            "subtask_ms": subtask_ms,
            "parallel_speedup": f"{sum(subtask_ms) / max(max(subtask_ms), 1):.1f}x"
        }
    }


# ── 测试 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== orchestrate.py 单元测试 ===\n")

    # 测试1：needs_orchestration 判断
    simple_intent = {"intent": "grbl_config", "complexity": 0.3}
    assert not needs_orchestration("GRBL怎么设置", simple_intent), "简单查询不应触发编排"

    complex_intent = {"intent": "unknown", "complexity": 0.9}
    complex_q = "请分别从硬件电路设计和软件编程两个角度，分析步进电机丢步问题的原因和解决方案"
    assert needs_orchestration(complex_q, complex_intent), "跨领域复杂查询应触发编排"
    print("[PASS] needs_orchestration 判断正确")

    # 测试2：decompose 回退
    fallback = decompose("简单问题")
    assert len(fallback) >= 1, "decompose 应至少返回1个子任务"
    assert fallback[0]["task"] == "简单问题", "解析失败应回退为原查询"
    print("[PASS] decompose 回退逻辑正确")

    print("\n=== 所有测试通过 ===")
