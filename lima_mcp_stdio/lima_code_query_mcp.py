#!/usr/bin/env python3
"""
LiMa Code Query MCP Server — 实时代码检索工具

包装 code_context/ 的语义检索 + graph_index 的关系查询，
让 Cursor/Kimi 可以直接通过 MCP 工具查询 LiMa 代码库。

工具：
- search_code: 语义搜索代码（按相关度返回文件）
- get_module_context: 获取模块结构（symbols + imports）
- find_related: 找关联文件（基于导入关系）
- trace_symbol: 追踪符号定义和引用
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path("D:/QWEN3.0")
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")


class LimaCodeQuery:
    """MCP 工具实现：包装 code_context 和 graph_index 的检索能力"""

    def __init__(self):
        self._index = None
        self._graph = None
        self._chroma = None
        self._init_index()
        self._cache: dict[str, Any] = {}

    def _init_index(self):
        """初始化 code_context 索引"""
        try:
            from code_context.index_store import build_code_index

            self._index = build_code_index()
        except Exception as e:
            pass  # 运行时初始化

        try:
            from code_context.sqlite_graph_store import SqliteGraphIndex

            self._graph = SqliteGraphIndex(str(PROJECT_ROOT / ".lima-data" / "graph.db"))
        except Exception:
            pass

    def search_code(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """语义搜索代码 — 返回相关文件和关键符号"""
        results = []

        # 1. 尝试 chroma 向量搜索
        try:
            from code_context.chroma_vector_store import ChromaCodeIndex

            chroma = ChromaCodeIndex(
                persist_directory=str(PROJECT_ROOT / ".lima-data"), collection_name="lima_code_index"
            )
            chroma_results = chroma.search(query, limit=limit)
            for r in chroma_results:
                results.append(
                    {
                        "path": r.get("path", ""),
                        "content": r.get("content", "")[:300],
                        "score": r.get("score", 0.0),
                        "source": "chroma",
                    }
                )
        except Exception:
            pass

        # 2. 符号匹配（基于 index_store 的关键词搜索）
        if self._index and len(results) < limit:
            try:
                keyword_results = self._index.search(query, limit=limit)
                for r in keyword_results:
                    symbols = [s.name for s in r.symbols]
                    imports = [imp[0] for imp in r.imports]
                    results.append(
                        {
                            "path": r.path,
                            "symbols": symbols[:10],
                            "imports": imports[:10],
                            "mtime": r.mtime,
                            "source": "keyword",
                        }
                    )
            except Exception:
                pass

        # 3. 文件路径匹配（直接扫关键目录）
        if len(results) < limit:
            query_lower = query.lower()
            KEY_DIRS = ["routes", "device_gateway", "device_intelligence", "context_pipeline", "session_memory"]
            for d in KEY_DIRS:
                dir_path = PROJECT_ROOT / d
                if not dir_path.exists():
                    continue
                for py_file in dir_path.rglob("*.py"):
                    if query_lower in py_file.stem.lower():
                        results.append({"path": str(py_file.relative_to(PROJECT_ROOT)), "source": "path_match"})
                    if len(results) >= limit * 2:
                        break
                if len(results) >= limit * 2:
                    break

        return results[:limit]

    def get_module_context(self, path: str) -> dict[str, Any]:
        """获取模块结构信息：符号、导入、文件大小"""
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            return {"error": f"File not found: {path}"}

        try:
            import ast

            source = full_path.read_text("utf-8", errors="replace")
            tree = ast.parse(source, filename=str(full_path))

            classes = []
            functions = []
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    classes.append({"name": node.name, "line": node.lineno, "methods": methods[:15]})
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append({"name": node.name, "line": node.lineno})
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({"name": alias.name, "line": node.lineno})
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        imports.append({"module": node.module, "name": alias.name, "line": node.lineno})

            return {
                "path": path,
                "size_bytes": full_path.stat().st_size,
                "lines": len(source.splitlines()),
                "classes": classes[:20],
                "functions": functions[:30],
                "imports": imports[:30],
            }
        except Exception as e:
            return {"error": str(e), "path": path}

    def find_related(self, path: str, max_results: int = 10) -> list[dict[str, Any]]:
        """找关联文件 — 基于导入关系 + 目录相邻"""
        related = []
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            return [{"error": f"File not found: {path}"}]

        # 1. 解析本文件的导入关系
        try:
            import ast

            source = full_path.read_text("utf-8", errors="replace")
            tree = ast.parse(source)
            local_imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        local_imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    local_imports.append(node.module)

            # 解析为文件路径
            for imp in local_imports:
                imp_path = imp.replace(".", "/") + ".py"
                # 尝试项目内路径
                candidates = [
                    PROJECT_ROOT / imp_path,
                    PROJECT_ROOT / path.replace("/", ".").split(".")[0] / imp_path.split("/")[-1],
                    PROJECT_ROOT / path.rsplit("/", 1)[0] / imp_path.split("/")[-1],
                ]
                for c in candidates:
                    if c.exists() and c != full_path:
                        rel = str(c.relative_to(PROJECT_ROOT))
                        if rel not in [r.get("path") for r in related]:
                            related.append({"path": rel, "relation": "imports"})
        except Exception:
            pass

        # 2. 同一目录相邻文件
        try:
            for f in full_path.parent.glob("*.py"):
                if f != full_path:
                    rel = str(f.relative_to(PROJECT_ROOT))
                    if rel not in [r.get("path") for r in related]:
                        related.append({"path": rel, "relation": "sibling"})
        except Exception:
            pass

        return related[:max_results]

    def trace_symbol(self, symbol_name: str, max_results: int = 15) -> list[dict[str, Any]]:
        """追踪符号定义和引用 — 跨文件搜索"""
        results = []
        KEY_DIRS = [
            "routes",
            "device_gateway",
            "device_intelligence",
            "context_pipeline",
            "routing_engine.py",
            "routing_classifier.py",
            "routing_selector.py",
        ]

        for search_dir in KEY_DIRS:
            search_path = PROJECT_ROOT / search_dir
            if not search_path.exists():
                continue
            if search_path.is_file():
                files = [search_path]
            else:
                files = search_path.rglob("*.py")

            for py_file in files:
                try:
                    source = py_file.read_text("utf-8", errors="replace")
                    for i, line in enumerate(source.splitlines(), 1):
                        if symbol_name in line:
                            line_stripped = line.strip()
                            if line_stripped.startswith("#"):
                                continue
                            results.append(
                                {
                                    "path": str(py_file.relative_to(PROJECT_ROOT)),
                                    "line": i,
                                    "code": line_stripped[:120],
                                    "type": "def" if "def " in line_stripped else "ref",
                                }
                            )
                except Exception:
                    pass

                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

        return results[:max_results]


# ===== MCP 协议实现 =====

code_query = LimaCodeQuery()


def handle_request(request: dict) -> dict:
    """处理 MCP JSON-RPC 请求"""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})
    tool_name = params.get("name", "")
    tool_args = params.get("arguments", {})

    # 工具列表
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "search_code",
                        "description": "语义搜索 LiMa 代码库，返回相关文件和符号",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "搜索关键词（支持模块名、函数名、概念）"},
                                "limit": {"type": "integer", "description": "返回结果数（默认8）"},
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_module_context",
                        "description": "获取模块结构信息：类、函数、导入关系",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "相对项目根目录的 Python 文件路径，如 routes/chat_handler.py",
                                }
                            },
                            "required": ["path"],
                        },
                    },
                    {
                        "name": "find_related",
                        "description": "找关联文件：基于导入关系和目录相邻",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "文件路径"},
                                "max_results": {"type": "integer", "description": "最大返回数"},
                            },
                            "required": ["path"],
                        },
                    },
                    {
                        "name": "trace_symbol",
                        "description": "跨文件追踪符号定义和引用",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "symbol_name": {"type": "string", "description": "符号名（函数/类/变量名）"},
                                "max_results": {"type": "integer"},
                            },
                            "required": ["symbol_name"],
                        },
                    },
                ]
            },
        }

    # 工具调用
    elif method == "tools/call":
        if tool_name == "search_code":
            result = code_query.search_code(tool_args.get("query", ""), tool_args.get("limit", 8))
        elif tool_name == "get_module_context":
            result = code_query.get_module_context(tool_args.get("path", ""))
        elif tool_name == "find_related":
            result = code_query.find_related(tool_args.get("path", ""), tool_args.get("max_results", 10))
        elif tool_name == "trace_symbol":
            result = code_query.trace_symbol(tool_args.get("symbol_name", ""), tool_args.get("max_results", 15))
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}]},
        }

    # 健康检查
    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "lima-code-query", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    """STDIO MCP 服务器入口"""
    import sys

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            error_response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
