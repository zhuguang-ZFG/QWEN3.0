#!/usr/bin/env python3
"""
LiMa Code Query Core — LimaCodeQuery class extracted from lima_code_query_mcp

包装 code_context/ 的语义检索 + graph_index 的关系查询。
"""

import logging
import sys
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


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
            logger.warning("code_context index init failed: %s", e)

        try:
            from code_context.sqlite_graph_store import SqliteGraphIndex

            self._graph = SqliteGraphIndex(str(PROJECT_ROOT / ".lima-data" / "graph.db"))
        except Exception as e:
            logger.warning("sqlite graph index init failed: %s", e)

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
                        "path": r.path,
                        "source": "chroma",
                    }
                )
        except Exception as e:
            logger.warning("chroma search failed for query %r: %s", query, e)

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
            except Exception as e:
                logger.warning("keyword index search failed for query %r: %s", query, e)

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
        except Exception as e:
            logger.warning("import parse failed for %s: %s", path, e)

        # 2. 同一目录相邻文件
        try:
            for f in full_path.parent.glob("*.py"):
                if f != full_path:
                    rel = str(f.relative_to(PROJECT_ROOT))
                    if rel not in [r.get("path") for r in related]:
                        related.append({"path": rel, "relation": "sibling"})
        except Exception as e:
            logger.warning("sibling scan failed for %s: %s", path, e)

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
                except Exception as e:
                    logger.warning("symbol trace read failed for %s: %s", py_file, e)

                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

        return results[:max_results]
