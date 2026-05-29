"""Graph-based context expansion — follow import/call chains to related files.

Uses the existing graph_index to expand a set of seed files into a
broader context window, limited by hop count and total file budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

_MAX_EXPANDED_FILES = 12
_DEFAULT_MAX_HOPS = 2


@dataclass
class ExpandedFile:
    file_path: str
    relationship_type: str  # import, call, extends, contains
    distance: int  # hops from seed
    relevance_reason: str


def expand_context(
    seed_files: list[str],
    project_root: str = "",
    max_hops: int = _DEFAULT_MAX_HOPS,
    max_files: int = _MAX_EXPANDED_FILES,
) -> list[ExpandedFile]:
    """Expand seed files into related context via graph traversal.

    Starting from seed files, follow import and call relationships
    up to max_hops depth, collecting up to max_files total results.
    """
    if not seed_files:
        return []

    try:
        from code_context.graph_index import build_graph_index
        graph = build_graph_index()
    except Exception as exc:
        _log.debug("graph expansion unavailable: %s", exc)
        return []

    expanded: list[ExpandedFile] = []
    visited: set[str] = set()

    for seed in seed_files:
        seed_name = Path(seed).stem
        if seed_name in visited:
            continue
        visited.add(seed_name)

        try:
            related = graph.search([seed_name], max_depth=max_hops, max_results=max_files)
            for r in related:
                rpath = str(r.entity)
                if rpath in visited or rpath in seed_files:
                    continue
                visited.add(rpath)

                rel_type = getattr(r, "relation_type", "related")
                distance = getattr(r, "distance", 1)
                reason = f"{rel_type} from {Path(seed).name} (depth {distance})"

                expanded.append(ExpandedFile(
                    file_path=rpath,
                    relationship_type=rel_type,
                    distance=distance,
                    relevance_reason=reason,
                ))

                if len(expanded) >= max_files:
                    return expanded
        except Exception:
            continue

    return expanded
