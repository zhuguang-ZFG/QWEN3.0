"""Admission decisions for no-login web AI candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BLOCKED_STATUSES = {
    "blocked",
    "auth_expired",
    "quota_exhausted",
    "manual_refresh_required",
}


def _probe_by_id(probes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("id", ""): item for item in probes if isinstance(item, dict)}


def decide_candidate(candidate: dict[str, Any],
                     probe: dict[str, Any] | None) -> dict[str, Any]:
    status = (probe or {}).get("status", "not_probed")
    reverse_status = candidate.get("reverse_status", "")
    admission_status = "sandbox_only"
    reason = "reachable page-only candidate; no hot-path adapter"

    if status in BLOCKED_STATUSES:
        admission_status = "rejected"
        reason = f"probe status is {status}"
    elif reverse_status == "already_reversed_local":
        if candidate.get("admission_passed") and status in ("ok", "not_probed"):
            admission_status = "admitted_late_fallback"
            reason = "local adapter and route admission evidence exist"
        else:
            admission_status = "sandbox_only"
            reason = "local adapter exists but admission evidence is incomplete"
    elif reverse_status == "adapter_draft_exists":
        admission_status = "adapter_draft_pending"
        reason = "adapter draft exists but model smoke is not admitted"
    elif reverse_status == "not_reversed_page_only":
        admission_status = "sandbox_only"

    return {
        "id": candidate["id"],
        "url": candidate["url"],
        "probe_status": status,
        "reverse_status": reverse_status or "unknown",
        "admission_status": admission_status,
        "route_allowed": admission_status == "admitted_late_fallback",
        "private_code_allowed": (
            admission_status == "admitted_late_fallback"
            and bool(candidate.get("private_code_allowed", False))
        ),
        "reason": reason,
    }


def build_admission(candidates: list[dict[str, Any]],
                    probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = _probe_by_id(probes)
    return [
        decide_candidate(candidate, by_id.get(candidate["id"]))
        for candidate in candidates
    ]


def write_json(path: str | Path, decisions: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: str | Path, decisions: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Free Web AI Admission",
        "",
        "> Updated: 2026-05-22",
        "> Private code remains disabled for no-login web candidates unless a candidate is explicitly admitted and trusted.",
        "",
        "| ID | Probe | Reverse Status | Admission | Route | Private Code | Reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in decisions:
        lines.append(
            "| {id} | {probe_status} | {reverse_status} | {admission_status} | "
            "{route_allowed} | {private_code_allowed} | {reason} |".format(**item)
        )
    lines.extend([
        "",
        "## Decision",
        "",
        "Only already-reversed, measured adapters may enter LiMa routing, and only as late fallback unless coding admission promotes them. Page-only candidates stay sandboxed.",
    ])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
