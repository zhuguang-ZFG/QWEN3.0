#!/usr/bin/env python3
"""Response examples for task management endpoints."""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_tasks_list() -> Any:
    return {"tasks": [{"id": uuid("tsk"), "status": "pending"}]}


def _resp_task_get() -> Any:
    return {"id": uuid("tsk"), "status": "done", "result_url": "https://example/result.png"}


def _resp_task_preview() -> Any:
    return {"preview_url": "https://example/preview.png"}


def _resp_task_templates_list() -> Any:
    return {"templates": [{"id": uuid("tpl"), "name": "Morning sketch"}]}


def _resp_task_templates_create() -> Any:
    return {"id": uuid("tpl"), "name": "Morning sketch"}


def _resp_task_template_execute() -> Any:
    return {"task_id": uuid("tsk"), "status": "queued"}


def _resp_task_save_as_template() -> Any:
    return {"template_id": uuid("tpl"), "saved": True}


def _resp_task_approve() -> Any:
    return {"task_id": uuid("tsk"), "status": "approved"}


def _resp_task_reject() -> Any:
    return {"task_id": uuid("tsk"), "status": "rejected"}


def _resp_task_timeline() -> Any:
    return {"events": [{"time": "2024-01-01T00:00:00Z", "status": "created"}]}
