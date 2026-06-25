"""Multi-device coordination — split large artwork across devices."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from device_gateway.sessions import registry
from device_gateway.store import task_store

_log = logging.getLogger(__name__)

_SVG_SIZE_RE = re.compile(r'width\s*=\s*"([0-9.]+)"', re.IGNORECASE)
_SVG_HEIGHT_RE = re.compile(r'height\s*=\s*"([0-9.]+)"', re.IGNORECASE)
_SVG_VIEWBOX_RE = re.compile(r'viewBox\s*=\s*"([^"]+)"', re.IGNORECASE)


def _fallback_parse_svg_bounds(svg_content: str) -> dict[str, float]:
    """Extract SVG canvas bounds from width/height or viewBox attributes."""
    width: float | None = None
    height: float | None = None
    x, y = 0.0, 0.0

    width_match = _SVG_SIZE_RE.search(svg_content)
    height_match = _SVG_HEIGHT_RE.search(svg_content)
    if width_match and height_match:
        width = float(width_match.group(1))
        height = float(height_match.group(1))

    viewbox_match = _SVG_VIEWBOX_RE.search(svg_content)
    if viewbox_match:
        parts = viewbox_match.group(1).strip().split()
        if len(parts) >= 4:
            try:
                x, y, vb_width, vb_height = (float(p) for p in parts[:4])
                width = width if width is not None else vb_width
                height = height if height is not None else vb_height
            except ValueError:
                _log.warning("SVG viewBox parse failed; using fallback defaults")

    if width is None or height is None:
        _log.warning("SVG width/height unavailable; defaulting to 200x200")
        width = width if width is not None else 200.0
        height = height if height is not None else 200.0

    return {"x": x, "y": y, "width": width, "height": height}


def _parse_svg_bounds(svg_content: str) -> dict[str, float]:
    """Use parser if available; otherwise fall back to regex extraction."""
    import device_gateway.svg_parser as _svg_parser_mod

    parse_svg_bounds = getattr(_svg_parser_mod, "parse_svg_bounds", None)
    if parse_svg_bounds is None:
        _log.warning("device_gateway.svg_parser.parse_svg_bounds unavailable; using regex fallback")
        return _fallback_parse_svg_bounds(svg_content)
    return parse_svg_bounds(svg_content)


class MultiDeviceCoordinator:
    """Split, assign, enqueue and summarize multi-device drawing tasks."""

    def split_artwork(self, svg_content: str, device_count: int) -> list[dict[str, Any]]:
        """Split SVG into per-device clipped regions."""
        bounds = _parse_svg_bounds(svg_content)
        regions = self._grid_split(bounds, device_count)
        return [
            {"device_index": i, "region": r, "svg_clip": self._clip_svg(svg_content, r)} for i, r in enumerate(regions)
        ]

    def _grid_split(self, bounds: dict[str, float], n: int) -> list[dict[str, float]]:
        """Divide a bounding box into an n-cell grid."""
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        cell_w = bounds["width"] / cols
        cell_h = bounds["height"] / rows
        regions: list[dict[str, float]] = []
        for row in range(rows):
            for col in range(cols):
                if len(regions) >= n:
                    break
                regions.append(
                    {
                        "x": bounds["x"] + col * cell_w,
                        "y": bounds["y"] + row * cell_h,
                        "width": cell_w,
                        "height": cell_h,
                    }
                )
        return regions

    def _clip_svg(self, svg_content: str, region: dict[str, float]) -> str:
        """Insert a clipPath and apply it to the first root <g>."""
        clip_id = f"clip_{region['x']}_{region['y']}"
        clip_def = (
            f'<defs><clipPath id="{clip_id}">'
            f'<rect x="{region["x"]}" y="{region["y"]}" '
            f'width="{region["width"]}" height="{region["height"]}"/>'
            f"</clipPath></defs>"
        )
        svg_with_clip = re.sub(
            r"(<svg[^>]*>)",
            rf"\g<1>{clip_def}",
            svg_content,
            count=1,
        )
        return re.sub(
            r"<g(?![^>]*clip-path)",
            f'<g clip-path="url(#{clip_id})"',
            svg_with_clip,
            count=1,
        )

    def assign_devices(self, regions: list[dict[str, Any]], device_ids: list[str]) -> list[dict[str, Any]]:
        """Attach a device_id to each region."""
        assignments: list[dict[str, Any]] = []
        for i, region in enumerate(regions[: len(device_ids)]):
            region_dict = region.get("region") if isinstance(region.get("region"), dict) else region
            assignments.append(
                {
                    "device_id": device_ids[i],
                    "device_index": i,
                    "region": region_dict,
                    "svg_clip": region.get("svg_clip", "") if "region" in region else "",
                }
            )
        return assignments

    def merge_results(self, device_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize per-device outcomes."""
        total = len(device_results)
        success = sum(1 for r in device_results if r.get("status") == "completed")
        failed = sum(1 for r in device_results if r.get("status") == "failed")
        overall = "completed" if total > 0 and success == total else "partial"
        if total == 0:
            overall = "empty"
        return {
            "total_devices": total,
            "success_count": success,
            "failed_count": failed,
            "overall_status": overall,
        }

    def _dispatch_one(
        self,
        svg_content: str,
        assignment: dict[str, Any],
        batch_id: str,
        coordinator_id: str,
    ) -> dict[str, Any]:
        """Build and enqueue a single coordinated task, or record offline."""
        from device_gateway.tasks import enqueue_pending_task

        device_id = assignment["device_id"]
        region = assignment["region"]
        session = registry.get(device_id)
        if session is None:
            return {"device_id": device_id, "status": "failed", "error": "device_offline"}

        clipped_svg = self._clip_svg(svg_content, region)
        task = {
            "task_id": task_store.next_task_id(),
            "device_id": device_id,
            "batch_id": batch_id,
            "coordinator_id": coordinator_id,
            "capability": "draw_svg",
            "params": {"svg": clipped_svg, "region": assignment},
        }
        enqueue_pending_task(device_id, task)
        return {"device_id": device_id, "task_id": task["task_id"], "status": "dispatched"}

    async def execute_coordinated(
        self,
        svg_content: str,
        device_ids: list[str],
        coordinator_id: str,
    ) -> dict[str, Any]:
        """Split artwork, assign devices, enqueue tasks, and return summary."""
        regions = self.split_artwork(svg_content, len(device_ids))
        assignments = self.assign_devices(regions, device_ids)
        batch_id = task_store.next_task_id()
        results = [self._dispatch_one(svg_content, assignment, batch_id, coordinator_id) for assignment in assignments]
        return {
            "batch_id": batch_id,
            "coordinator_id": coordinator_id,
            "results": results,
            "summary": self.merge_results(results),
        }
