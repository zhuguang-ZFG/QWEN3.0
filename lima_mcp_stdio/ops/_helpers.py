"""Shared helpers for Lima ops tools."""

from __future__ import annotations


def _filter_servers(servers: dict | None, host: str | None) -> dict:
    """根据 host 过滤服务器字典。

    host 为 None 时返回全部；servers 为 None 时返回空字典。
    匹配规则：host 是 shost 或 label 的子串。
    """
    if servers is None:
        return {}
    if host is None:
        return servers
    return {sh: info for sh, info in servers.items() if host in sh or host in info.get("label", "")}


def _format_result(label: str, shost: str | None = None, body: str = "", summary: bool = True) -> str:
    """格式化单条结果。

    summary=True  返回紧凑格式  → [label] body
    summary=False 返回详细块头  → \n=== label (shost) ===
    """
    if summary:
        return f"[{label}] {body}"
    return f"\n=== {label} ({shost}) ==="
