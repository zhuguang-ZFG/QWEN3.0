#!/usr/bin/env python3
"""提取 LiMa 设备-云端 API 契约知识"""

import ast, os
from pathlib import Path
from collections import defaultdict

PROJECT = Path("D:/QWEN3.0")

# 设备相关路由
DEVICE_ROUTES = [
    "routes/device_gateway_ws.py",
    "routes/device_proxy.py",
    "routes/device_files.py",
    "routes/query_device_handler.py",
    "routes/task_handler.py",
    "routes/device_admin_handler.py",
    "routes/device_group_handler.py",
    "routes/device_count_handler.py",
    "routes/ota_handler.py",
    "routes/device_manage_handler.py",
]

# 设备网关核心
DEVICE_GATEWAY = sorted(Path(PROJECT / "device_gateway").rglob("*.py"))


def extract_api_endpoints(filepath):
    """提取 FastAPI 路由"""
    full = PROJECT / filepath
    if not full.exists():
        return []
    try:
        source = full.read_text("utf-8", errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return []

    endpoints = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 装饰器分析
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    if hasattr(dec.func, "attr"):
                        method = dec.func.attr  # get/post/put/delete/ws
                        if method in ("get", "post", "put", "delete", "ws", "websocket"):
                            # 提取路径
                            args = [a for a in dec.args if isinstance(a, ast.Constant)]
                            if args:
                                endpoints.append(
                                    {
                                        "file": filepath,
                                        "method": method.upper() if method != "ws" else "WS",
                                        "path": args[0].value,
                                        "function": node.name,
                                        "line": node.lineno,
                                    }
                                )
        elif isinstance(node, ast.AsyncFunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    if hasattr(dec.func, "attr"):
                        method = dec.func.attr
                        if method in ("get", "post", "put", "delete", "ws", "websocket"):
                            args = [a for a in dec.args if isinstance(a, ast.Constant)]
                            if args:
                                endpoints.append(
                                    {
                                        "file": filepath,
                                        "method": method.upper() if method != "ws" else "WS",
                                        "path": args[0].value,
                                        "function": node.name,
                                        "line": node.lineno,
                                    }
                                )

    return endpoints


def extract_device_protocols():
    """提取设备协议定义"""
    protocols = defaultdict(list)
    for py in DEVICE_GATEWAY:
        try:
            source = py.read_text("utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        rel = str(py.relative_to(PROJECT))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 类名包含 Protocol/Handler/Gateway 的是关键协议类
                if any(k in node.name for k in ("Protocol", "Handler", "Gateway", "Session", "Task", "Family")):
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    protocols[rel].append(
                        {
                            "class": node.name,
                            "line": node.lineno,
                            "methods": methods[:10],
                        }
                    )

    return protocols


def main():
    print("=== 设备端 API 端点 ===")
    all_endpoints = []
    for rf in DEVICE_ROUTES:
        eps = extract_api_endpoints(rf)
        all_endpoints.extend(eps)
        for ep in eps:
            print(f"  {ep['method']:6s} {ep['path']:40s} → {ep['function']} ({ep['file']}:{ep['line']})")

    print(f"\n总端点: {len(all_endpoints)}")

    # 按路径模式分组
    groups = defaultdict(list)
    for ep in all_endpoints:
        parts = ep["path"].strip("/").split("/")
        pattern = "/" + "/".join(parts[:2]) if len(parts) >= 2 else "/" + parts[0]
        groups[pattern].append(ep["method"])

    print("\n=== API 模式分组 ===")
    for pattern, methods in sorted(groups.items()):
        methods_set = sorted(set(methods))
        print(f"  {pattern:40s} [{', '.join(methods_set)}] ({len(methods)})")

    # 协议类
    print("\n=== 设备网关协议类 ===")
    protocols = extract_device_protocols()
    for filepath, classes in sorted(protocols.items()):
        for c in classes:
            methods_str = ", ".join(c["methods"][:6])
            print(f"  {c['class']:35s} ({filepath})")
            print(f"    方法: {methods_str}")

    # 生成架构知识
    print("\n=== 架构总结 ===")
    # 协议族
    print("设备协议层:")
    for filepath, classes in sorted(protocols.items()):
        for c in classes:
            if "Protocol" in c["class"]:
                print(f"  - {c['class']}")

    print("\n设备状态层:")
    for filepath, classes in sorted(protocols.items()):
        for c in classes:
            if "State" in c["class"] or "Session" in c["class"]:
                print(f"  - {c['class']}")

    print("\n任务系统层:")
    for filepath, classes in sorted(protocols.items()):
        for c in classes:
            if "Task" in c["class"] or "Job" in c["class"]:
                print(f"  - {c['class']}")


if __name__ == "__main__":
    main()
