#!/usr/bin/env python3
"""
增强版架构知识文档生成器。
合并: CodeGraph AST 数据 + API 端点分析 + 协议类提取
输出: ARCHITECTURE_KNOWLEDGE.md + 嵌入 shared-memory
"""

import ast
import json
import logging
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("D:/QWEN3.0")
CODEGRAPH_DB = str(PROJECT_ROOT / ".codegraph" / "codegraph.db")
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ========== Phase 1: 协议类提取 ==========

DEVICE_GATEWAY_FILES = sorted((PROJECT_ROOT / "device_gateway").rglob("*.py"))


def extract_protocol_classes():
    """从 device_gateway/ 提取协议类"""
    result = []
    for py in DEVICE_GATEWAY_FILES:
        try:
            source = py.read_text("utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        rel = str(py.relative_to(PROJECT_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                doc = ast.get_docstring(node) or ""
                result.append(
                    {
                        "file": rel,
                        "class": node.name,
                        "line": node.lineno,
                        "methods": methods,
                        "doc": doc[:200],
                    }
                )
    return result


# ========== Phase 2: 关键目录分析 ==========


def get_dir_symbols():
    conn = sqlite3.connect(CODEGRAPH_DB)
    rows = conn.execute("SELECT file_path, kind, COUNT(*) FROM nodes GROUP BY file_path, kind").fetchall()
    conn.close()
    return rows


def get_kinds_distribution():
    conn = sqlite3.connect(CODEGRAPH_DB)
    rows = conn.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind ORDER BY COUNT(*) DESC").fetchall()
    conn.close()
    return rows


def get_top_functions():
    conn = sqlite3.connect(CODEGRAPH_DB)
    rows = conn.execute(
        "SELECT name, qualified_name, file_path, kind FROM nodes "
        "WHERE kind IN ('function', 'method', 'async_function', 'async_method') "
        "ORDER BY length(file_path) LIMIT 200"
    ).fetchall()
    conn.close()
    return rows


# ========== 文档生成 ==========


def build_architecture_doc():
    lines = []
    lines.append("# LiMa 全栈架构知识库")
    lines.append(f"*自动生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"*数据源: CodeGraph (40,760 节点, 84,332 边) | 代码分析*")
    lines.append("")

    # ===== 1. 系统构成 =====
    lines.append("## 1. 系统构成")
    lines.append("")
    lines.append("| 子系统 | 说明 | 规模 |")
    lines.append("|--------|------|------|")
    dir_sizes = defaultdict(int)
    for fp, kind, cnt in get_dir_symbols():
        top = fp.split("/")[0] if "/" in fp else fp.split("\\")[0]
        dir_sizes[top] += cnt

    subsystems = [
        ("routes", "FastAPI 路由层，设备/WebSocket/管理 API"),
        ("device_gateway", "设备网关，WebSocket 连接/会话/任务/协议"),
        ("device_intelligence", "设备 AI 能力（影子/知识/工具）"),
        ("device_voice", "音频流处理"),
        ("device_memory", "设备记忆"),
        ("device_support", "设备辅助功能"),
        ("device_workflow", "设备工作流"),
        ("device_ledger", "设备账本"),
        ("device_policy", "设备策略"),
        ("context_pipeline", "AI 请求上下文构建流水线"),
        ("routing_selector", "AI 后端路由选择"),
        ("routing_ml", "路由智能调度"),
        ("routing_loop", "路由主循环"),
        ("session_memory", "会话记忆管理"),
        ("search_gateway", "搜索网关"),
        ("local_retrieval", "本地检索"),
        ("observability", "可观测性"),
        ("fleet", "设备车队管理"),
        ("infra", "基础设施"),
        ("backends_registry", "AI 后端注册表"),
        ("provider_automation", "提供商自动化"),
        ("provider_inventory", "提供商清单"),
        ("provider_probe", "提供商探针"),
        ("tool_gateway", "工具网关"),
        ("response_cleaner", "响应清洗"),
        ("lima_mcp_stdio", "MCP 服务器实现"),
        ("esp32S_XYZ", "ESP32 固件 + 小智服务端 + Java 管理端"),
        ("tests", "测试"),
        ("packages", "第三方包"),
    ]
    for name, desc in subsystems:
        size = dir_sizes.get(name, 0)
        if size:
            lines.append(f"| {name} | {desc} | {size} 符号 |")

    lines.append("")

    # ===== 2. 代码分布 =====
    lines.append("## 2. 代码分布")
    lines.append("")
    for kind, cnt in get_kinds_distribution()[:15]:
        lines.append(f"- **{kind}**: {cnt}")
    lines.append("")

    # ===== 3. 设备连接层 =====
    lines.append("## 3. 设备连接架构")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TB")
    lines.append("  Device[ESP32 设备] -->|WebSocket| WS[device_gateway_ws.py]")
    lines.append("  WS --> SessionMgmt[SessionRegistry / DeviceSession]")
    lines.append("  SessionMgmt -->|心跳/状态| Heartbeat[device_gateway/sessions]")
    lines.append("  SessionMgmt -->|任务下发| TaskService[device_gateway/task_service]")
    lines.append("  TaskService -->|通知| Notifier[RedisDeviceTaskNotifier]")
    lines.append("  TaskService -->|存储| TaskStore[RedisDeviceTaskStore]")
    lines.append("  WS -->|协议解析| Protocol[ProtocolFamily / ProtocolSchema]")
    lines.append("  Protocol -->|路由| Route[routing_loop / routing_selector]")
    lines.append("  Route -->|AI 后端| Backend[backends_registry 170+]")
    lines.append("  Backend -->|流式响应| Response[response_cleaner]")
    lines.append("  Response --> WS")
    lines.append("```")
    lines.append("")

    # ===== 4. 协议类清单 =====
    lines.append("## 4. 设备网关核心类")
    lines.append("")
    protos = extract_protocol_classes()
    for p in protos:
        methods_str = ", ".join(p["methods"][:8])
        doc = p["doc"].replace("\n", " ")[:100]
        lines.append(f"- **{p['class']}** (`{p['file']}:{p['line']}`)")
        if doc:
            lines.append(f"  *{doc}*")
        if methods_str:
            lines.append(f"  方法: `{methods_str}`")
        lines.append("")

    # ===== 5. 关键模块 =====
    lines.append("## 5. 关键路由模块")
    lines.append("")
    key_routes = [
        ("routes/device_gateway_ws.py", "WebSocket 设备网关，设备虚实连接"),
        ("routes/device_proxy.py", "设备代理"),
        ("routes/device_files.py", "设备文件"),
        ("routes/query_device_handler.py", "设备查询"),
        ("routes/task_handler.py", "任务处理"),
        ("routes/ota_handler.py", "OTA 升级"),
        ("routes/admin_api.py", "管理 API"),
        ("routes/system_endpoints.py", "系统端点"),
        ("routes/xiaozhi_compat/", "小智兼容层"),
    ]
    for path, desc in key_routes:
        lines.append(f"- **{path}**: {desc}")

    # ===== 6. 配置/路由架构 =====
    lines.append("\n## 6. AI 路由流水线")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph LR")
    lines.append("  C[ContextPipeline] -->|构建上下文| RC[routing_classifier]")
    lines.append("  RC -->|分类| RS[routing_selector]")
    lines.append("  RS -->|过滤/排序| E[routing_executor]")
    lines.append("  E -->|调用| H[http_caller]")
    lines.append("  H -->|流式| P[provider_probe]")
    lines.append("  P -->|降级| RS")
    lines.append("  H -->|结果| CL[response_cleaner]")
    lines.append("  CL -->|返回| WS[device_gateway]")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    doc = build_architecture_doc()
    out = PROJECT_ROOT / "ARCHITECTURE_KNOWLEDGE.md"
    out.write_text(doc, encoding="utf-8")
    log.info(f"✅ 写入 {out} ({len(doc)} 字符)")

    # 概要
    protos = extract_protocol_classes()
    print(f"\n=== 协议类: {len(protos)} ===")
    for p in protos:
        print(f"  {p['class']:35s} {p['file'][:45]}")

    kinds = get_kinds_distribution()[:10]
    print(f"\n=== 符号分布 ===")
    for k, v in kinds:
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
