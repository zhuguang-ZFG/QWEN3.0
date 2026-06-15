"""Parse and merge JSON findings from MiMo lane output."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def extract_json_arrays(text: str) -> list[Any]:
    items: list[Any] = []
    seen: set[str] = set()

    def add_array(data: list[Any]) -> None:
        for entry in data:
            if not isinstance(entry, dict):
                continue
            key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            items.append(entry)

    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    sources = blocks if blocks else [text]
    for chunk in sources:
        add_array(_parse_array(chunk))
    return items


def _parse_array(text: str) -> list[Any]:
    text = text.strip()
    if not text:
        return []
    for match in re.finditer(r"\[\s*\{[\s\S]*?\}\s*\]", text):
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            return data
    return []


def normalize_finding(raw: dict[str, Any], default_lane: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    lane = str(raw.get("lane") or default_lane).strip().lower()
    severity = str(raw.get("severity") or "P2").strip().upper()
    if severity not in SEVERITY_ORDER:
        severity = "P2"
    fid = str(raw.get("id") or "").strip() or _auto_id(title)
    item = {
        "id": fid,
        "lane": lane,
        "severity": severity,
        "title": title,
        "file": str(raw.get("file") or "").strip(),
        "line": raw.get("line"),
        "evidence": str(raw.get("evidence") or "").strip(),
        "fix_hint": str(raw.get("fix_hint") or "").strip(),
        "test": str(raw.get("test") or "").strip(),
        "lanes": [lane],
    }
    if not item["evidence"]:
        return None
    return item


def _auto_id(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:24]
    return slug or "finding"


def _dedupe_key(item: dict[str, Any]) -> str:
    file_part = item.get("file") or ""
    line_part = item.get("line") or ""
    title = re.sub(r"\s+", " ", item["title"].lower()).strip()
    return f"{file_part}|{line_part}|{title}"


def merge_lane_artifacts(artifact_dir: Path, lanes: tuple[str, ...]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for lane in lanes:
        path = artifact_dir / f"{lane}.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.startswith("ERROR:") or text.startswith("SKIPPED:"):
            continue
        for raw in extract_json_arrays(text):
            if not isinstance(raw, dict):
                continue
            item = normalize_finding(raw, lane)
            if not item:
                continue
            key = _dedupe_key(item)
            if key in merged:
                existing = merged[key]
                for extra in item["lanes"]:
                    if extra not in existing["lanes"]:
                        existing["lanes"].append(extra)
                if SEVERITY_ORDER[item["severity"]] < SEVERITY_ORDER[existing["severity"]]:
                    existing["severity"] = item["severity"]
            else:
                merged[key] = item
    findings = list(merged.values())
    findings.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["id"]))
    return findings


def write_findings_bundle(
    artifact_dir: Path,
    findings: list[dict[str, Any]],
    lane_results: list[dict[str, Any]],
    task: str,
    mode: str,
) -> tuple[Path, Path, Path]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "generated_at": now,
        "task": task,
        "mode": mode,
        "lane_results": lane_results,
        "findings": findings,
        "summary": _summarize(findings),
    }
    findings_path = artifact_dir / "findings.json"
    findings_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    synthesis_path = artifact_dir / "synthesis.md"
    synthesis_path.write_text(_render_synthesis(payload), encoding="utf-8")
    fixpack_path = artifact_dir / "fix-pack.md"
    fixpack_path.write_text(_render_fix_pack(findings), encoding="utf-8")
    return findings_path, synthesis_path, fixpack_path


def compare_findings_lists(
    old_items: list[dict[str, Any]],
    new_findings: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    old_keys = {_dedupe_key(i) for i in old_items}
    new_keys = {_dedupe_key(i) for i in new_findings}
    closed = [i for i in old_items if _dedupe_key(i) not in new_keys]
    still_open = [i for i in new_findings if _dedupe_key(i) in old_keys]
    new_only = [i for i in new_findings if _dedupe_key(i) not in old_keys]
    return {"closed": closed, "still_open": still_open, "new": new_only}


def _summarize(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in findings:
        sev = item.get("severity", "P2")
        if sev in counts:
            counts[sev] += 1
    return counts


def _render_synthesis(payload: dict[str, Any]) -> str:
    lines = [
        "# MiMo MCP Synthesis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- mode: {payload['mode']}",
        f"- task: {payload['task']}",
        "",
        "## Finding counts",
        "",
    ]
    summary = payload.get("summary", {})
    for key in ("P0", "P1", "P2", "P3"):
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines.extend(["", "## Findings", ""])
    for item in payload.get("findings", []):
        loc = ""
        if item.get("file"):
            loc = f" (`{item['file']}`"
            if item.get("line"):
                loc += f":{item['line']}"
            loc += ")"
        lines.append(f"- **{item['severity']} {item['id']}** {item['title']}{loc}")
    lines.append("")
    return "\n".join(lines)


def _render_fix_pack(findings: list[dict[str, Any]]) -> str:
    actionable = [f for f in findings if f.get("severity") in {"P0", "P1"}]
    lines = ["# MiMo MCP Fix Pack", ""]
    if not actionable:
        lines.append("- (no P0/P1 findings with evidence)")
        lines.append("")
        return "\n".join(lines)
    for item in actionable:
        lines.append(f"## {item['severity']} {item['id']}: {item['title']}")
        if item.get("file"):
            lines.append(f"- file: `{item['file']}`")
        if item.get("evidence"):
            lines.append(f"- evidence: {item['evidence']}")
        if item.get("fix_hint"):
            lines.append(f"- fix: {item['fix_hint']}")
        if item.get("test"):
            lines.append(f"- test: `{item['test']}`")
        lines.append("")
    return "\n".join(lines)
