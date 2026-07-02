#!/usr/bin/env python3
"""
LiMa CodeGraph Impact Analysis — 工具函数和 DB 层。
从 lima_codegraph_mcp.py 拆分而来，供 handle_request/main 调用。
"""

import json
import os
from collections import defaultdict
from pathlib import Path

from config.sqlite_pool import get_pooled_connection

CODEGRAPH_DB = "D:/QWEN3.0/.codegraph/codegraph.db"


def db():
    return get_pooled_connection(CODEGRAPH_DB)


# ========== 工具函数 ==========


def tool_impact_analysis(symbol_name: str, depth: int = 1) -> str:
    """
    影响分析：修改/删除指定符号，会影响到哪些模块？

    算法: 从 symbol 出发，沿调用边反向追踪所有调用者。
    depth=1: 直接调用者; depth=2: 调用者的调用者
    """
    conn = db()

    # 查找符号
    node = conn.execute(
        "SELECT id, name, qualified_name, file_path, kind FROM nodes "
        "WHERE name=? OR qualified_name LIKE ? OR qualified_name LIKE ? LIMIT 5",
        (symbol_name, f"%.{symbol_name}", f"{symbol_name}%"),
    ).fetchall()

    if not node:
        conn.close()
        return json.dumps(
            {"error": f"符号 '{symbol_name}' 未找到", "suggestions": _suggest_symbols(conn, symbol_name)},
            ensure_ascii=False,
        )

    results = []
    for nid, name, qname, fpath, kind in node:
        impact = _trace_callers(conn, nid, depth)
        results.append(
            {
                "symbol": name,
                "qualified_name": qname,
                "file": fpath,
                "kind": kind,
                "impact_chain": impact,
                "total_downstream": len([i for i in impact if i.get("level", 0) <= depth]),
            }
        )

    conn.close()
    return json.dumps({"query": symbol_name, "results": results, "depth": depth}, ensure_ascii=False, indent=2)


def _trace_callers(conn, node_id: str, max_depth: int) -> list:
    """反向追踪调用者"""
    result = []
    visited = set()

    def trace(nid, depth):
        if depth > max_depth or nid in visited:
            return
        visited.add(nid)

        callers = conn.execute(
            "SELECT source FROM edges WHERE target=? AND (kind='calls' OR kind='references')", (nid,)
        ).fetchall()

        for (src_id,) in callers:
            row = conn.execute("SELECT name, file_path, kind FROM nodes WHERE id=?", (src_id,)).fetchone()
            if row:
                result.append(
                    {
                        "source": row[0],
                        "file": row[1],
                        "kind": row[2],
                        "level": depth,
                    }
                )
                trace(src_id, depth + 1)

    trace(node_id, 1)
    return result


def tool_dependency_analysis(symbol_name: str) -> str:
    """
    依赖分析：X 依赖了哪些模块/符号？

    沿调用边正向追踪 X 调用的所有符号。
    """
    conn = db()

    node = conn.execute(
        "SELECT id, name, qualified_name, file_path FROM nodes WHERE name=? OR qualified_name LIKE ? LIMIT 3",
        (symbol_name, f"%.{symbol_name}"),
    ).fetchall()

    if not node:
        conn.close()
        return json.dumps({"error": f"符号 '{symbol_name}' 未找到"}, ensure_ascii=False)

    results = []
    for nid, name, qname, fpath in node:
        dep_list = _fetch_symbol_dependencies(conn, nid)
        results.append({"symbol": name, "file": fpath, "dependencies": dep_list})

    conn.close()
    return json.dumps({"query": symbol_name, "results": results}, ensure_ascii=False, indent=2)


def tool_search_symbols(query: str, limit: int = 15) -> str:
    """
    FTS5 全文搜索：搜索代码符号（函数/类/方法）

    使用 CodeGraph 内置的 FTS5 索引，支持模糊搜索。
    """
    conn = db()

    fts_query = _build_fts_query(query)

    rows = conn.execute(
        "SELECT n.id, n.name, n.qualified_name, n.file_path, n.kind, n.docstring "
        "FROM nodes n "
        "JOIN nodes_fts fts ON n.id = fts.id "
        "WHERE nodes_fts MATCH ? "
        "ORDER BY rank "
        "LIMIT ?",
        (fts_query, limit),
    ).fetchall()

    # 回退：LIKE 搜索
    if not rows:
        rows = conn.execute(
            "SELECT id, name, qualified_name, file_path, kind, docstring "
            "FROM nodes "
            "WHERE name LIKE ? OR qualified_name LIKE ? "
            "LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        method = "like"
    else:
        method = "fts5"

    results = _format_symbol_rows(rows)
    conn.close()
    return json.dumps({"method": method, "query": query, "results": results}, ensure_ascii=False, indent=2)


def tool_module_structure(module_path: str) -> str:
    """
    模块结构：分析指定目录/文件的结构

    返回该目录下所有文件的符号统计 + 依赖关系
    """
    conn = db()

    pattern = f"%{module_path.replace('/', os.sep)}%"

    files = conn.execute(
        "SELECT DISTINCT file_path, COUNT(*) as cnt FROM nodes "
        "WHERE file_path LIKE ? GROUP BY file_path ORDER BY cnt DESC LIMIT 30",
        (pattern,),
    ).fetchall()

    # 模块间依赖
    file_list = [f[0] for f in files]
    dependencies = _compute_module_dependencies(conn, file_list)

    conn.close()

    return json.dumps(
        {
            "module": module_path,
            "files": [{"path": f[0], "symbols": f[1]} for f in files],
            "internal_dependencies": dict(sorted(dependencies.items(), key=lambda x: -x[1])[:20]),
        },
        ensure_ascii=False,
        indent=2,
    )


def _suggest_symbols(conn, partial: str) -> list:
    """建议相似符号名"""
    rows = conn.execute("SELECT name, file_path FROM nodes WHERE name LIKE ? LIMIT 10", (f"%{partial}%",)).fetchall()
    return [{"name": r[0], "file": r[1]} for r in rows]


def _fetch_symbol_dependencies(conn, nid) -> list[dict]:
    """获取符号的依赖列表（调用/导入边），限 30 条。"""
    deps = conn.execute(
        "SELECT target, kind FROM edges WHERE source=? AND (kind='calls' OR kind='imports')", (nid,)
    ).fetchall()
    dep_list: list[dict] = []
    for tgt, kind in deps[:30]:
        tgt_row = conn.execute("SELECT name, file_path FROM nodes WHERE id=?", (tgt,)).fetchone()
        if tgt_row:
            dep_list.append({"name": tgt_row[0], "file": tgt_row[1], "relation": kind})
    return dep_list


def _build_fts_query(query: str) -> str:
    """将用户查询转换为 FTS5 MATCH 表达式。"""
    words = query.replace(" ", " AND ")
    return f'"{words}"' if len(query.split()) == 1 else f"({words})"


def _format_symbol_rows(rows) -> list[dict]:
    """将 nodes 行格式化为搜索结果字典列表。"""
    return [
        {
            "symbol": name,
            "qualified": qname,
            "file": fpath,
            "kind": kind,
            "doc": (doc or "")[:100],
        }
        for nid, name, qname, fpath, kind, doc in rows
    ]


def _compute_module_dependencies(conn, file_list: list[str]) -> dict:
    """计算模块内文件间依赖计数，返回 {“f1 → f2”: count}。"""
    dependencies: dict[str, int] = defaultdict(int)
    for f1_id in file_list[:20]:
        f1_node = conn.execute("SELECT id FROM nodes WHERE file_path=? AND kind='file' LIMIT 1", (f1_id,)).fetchone()
        if not f1_node:
            continue
        for f2_id in file_list[:20]:
            if f1_id == f2_id:
                continue
            f2_node = conn.execute(
                "SELECT id FROM nodes WHERE file_path=? AND kind='file' LIMIT 1", (f2_id,)
            ).fetchone()
            if not f2_node:
                continue
            cnt = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE source=? AND target=?", (f1_node[0], f2_node[0])
            ).fetchone()[0]
            if cnt > 0:
                dependencies[f"{os.path.basename(f1_id)} → {os.path.basename(f2_id)}"] = cnt
    return dependencies


# ========== 工具注册表 ==========

TOOLS = {
    "impact_analysis": {
        "description": "影响分析：修改/删除某符号后，追踪哪些代码会被影响。输入符号名（函数/类名），返回调用者链。",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol_name": {"type": "string", "description": "函数名/类名/变量名"},
                "depth": {"type": "integer", "description": "追踪深度 (1=直接调用者, 2=间接)", "default": 1},
            },
            "required": ["symbol_name"],
        },
    },
    "dependency_analysis": {
        "description": "依赖分析：指定符号依赖了哪些其他模块/符号。输入符号名，返回它所调用的所有符号。",
        "parameters": {
            "type": "object",
            "properties": {"symbol_name": {"type": "string", "description": "函数名/类名/变量名"}},
            "required": ["symbol_name"],
        },
    },
    "search_symbols": {
        "description": "FTS5 全文搜索代码符号。支持模糊匹配和docstring搜索。输入关键词，返回匹配的符号列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 15},
            },
            "required": ["query"],
        },
    },
    "module_structure": {
        "description": "模块结构分析：查看指定目录/模块的代码结构，包括文件清单、符号统计和内部依赖关系。",
        "parameters": {
            "type": "object",
            "properties": {
                "module_path": {"type": "string", "description": "目录路径，如 'device_gateway' 或 'routes'"}
            },
            "required": ["module_path"],
        },
    },
}
