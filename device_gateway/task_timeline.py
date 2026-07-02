"""设备任务历史时间线查询 — 将原始 ledger 事件转为结构化时间线。

之前 `GET /tasks/{task_id}` 返回原始事件列表，无法直观看到状态流转和耗时。
本模块将 ledger 事件流转换为带时间戳、状态描述、阶段耗时的结构化时间线。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from device_ledger.events import LedgerEvent
from device_ledger import store as _ledger_store_mod

# 终态阶段
_TERMINAL_PHASES = frozenset({"done", "failed", "cancelled", "dead_letter"})

# 状态中文描述映射
_PHASE_LABELS: dict[str, str] = {
    "created": "任务创建",
    "queued": "排队等待",
    "dispatching": "分发中",
    "dispatched": "已分发至设备",
    "processing": "设备处理中",
    "executing": "执行绘图/写字",
    "paused": "已暂停",
    "resumed": "已恢复",
    "done": "完成",
    "failed": "失败",
    "cancelled": "已取消",
    "dead_letter": "死信（放弃）",
}


def _parse_timestamp(iso_str: str) -> datetime | None:
    """解析 ISO 时间戳字符串。"""
    if not iso_str:
        return None
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _label_for_event(event: LedgerEvent) -> str:
    """根据事件类型生成人类可读的描述。"""
    etype = event.event_type
    if etype == "task_created":
        return _PHASE_LABELS.get("created", "任务创建")
    if etype == "task_dispatched":
        return _PHASE_LABELS.get("dispatched", "已分发至设备")
    if etype == "motion_event":
        phase = str(event.payload.get("motion_event", {}).get("phase", ""))
        return _PHASE_LABELS.get(phase, phase or "运动事件")
    if etype == "task_terminal":
        phase = str(event.payload.get("terminal_event", {}).get("phase", ""))
        return _PHASE_LABELS.get(phase, phase or "终态")
    if etype == "task_acknowledged":
        return "设备已确认"
    if etype == "task_progress":
        return "进度更新"
    if etype == "task_paused":
        return _PHASE_LABELS.get("paused", "已暂停")
    if etype == "task_resumed":
        return _PHASE_LABELS.get("resumed", "已恢复")
    if etype == "device_connected":
        return "设备已连接"
    if etype == "device_disconnected":
        return "设备已断开"
    return etype


def _extract_phase(event: LedgerEvent) -> str:
    """从事件中提取阶段名称。"""
    if event.event_type == "task_created":
        return str(event.payload.get("status", "created"))
    if event.event_type == "task_dispatched":
        return "dispatched"
    if event.event_type == "motion_event":
        return str(event.payload.get("motion_event", {}).get("phase", ""))
    if event.event_type == "task_terminal":
        return str(event.payload.get("terminal_event", {}).get("phase", ""))
    return event.event_type


def build_task_timeline(task_id: str) -> dict[str, Any] | None:
    """构建单个任务的时间线。

    Returns:
        包含 task_id、current_status、is_terminal、timeline 列表的字典，
        若任务不存在则返回 None。
    """
    events = _ledger_store_mod.ledger_store.events_for_task(task_id)
    if not events:
        return None

    timeline: list[dict[str, Any]] = []
    prev_ts: datetime | None = None
    current_status = "unknown"

    for event in events:
        ts = _parse_timestamp(event.created_at)
        duration_ms = 0
        if prev_ts and ts:
            delta = (ts - prev_ts).total_seconds() * 1000
            duration_ms = int(max(0, delta))

        phase = _extract_phase(event)
        if phase:
            current_status = phase

        entry: dict[str, Any] = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.created_at,
            "phase": phase,
            "label": _label_for_event(event),
            "duration_ms": duration_ms,
        }
        timeline.append(entry)
        prev_ts = ts

    is_terminal = current_status in _TERMINAL_PHASES
    total_duration_ms = sum(e["duration_ms"] for e in timeline)

    return {
        "task_id": task_id,
        "device_id": events[0].device_id if events else "",
        "current_status": current_status,
        "is_terminal": is_terminal,
        "event_count": len(events),
        "total_duration_ms": total_duration_ms,
        "timeline": timeline,
    }


def build_device_timeline(
    device_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """构建设备级别的时间线 — 聚合该设备所有任务的状态流转。

    按时间倒序排列，最多返回 limit 条。
    """
    events = _ledger_store_mod.ledger_store.events_for_device(device_id)
    if not events:
        return []

    # 按时间正序处理，构建每个任务的时间线
    task_timelines: dict[str, dict[str, Any]] = {}
    for event in events:
        tid = event.task_id
        if tid not in task_timelines:
            task_timelines[tid] = {
                "task_id": tid,
                "device_id": device_id,
                "first_seen": event.created_at,
                "last_seen": event.created_at,
                "event_count": 0,
                "phases": [],
                "current_status": "unknown",
            }
        tl = task_timelines[tid]
        tl["event_count"] += 1
        tl["last_seen"] = event.created_at
        phase = _extract_phase(event)
        if phase:
            tl["current_status"] = phase
            tl["phases"].append({"phase": phase, "label": _label_for_event(event), "timestamp": event.created_at})

    # 按最后更新时间倒序排列
    result = sorted(task_timelines.values(), key=lambda t: t["last_seen"], reverse=True)
    for item in result:
        item["is_terminal"] = item["current_status"] in _TERMINAL_PHASES
    return result[:limit]
