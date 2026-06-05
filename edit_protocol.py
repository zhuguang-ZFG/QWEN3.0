"""SEARCH/REPLACE edit protocol for LiMa.

The protocol is deterministic and auditable. It is inspired by Aider-style
SEARCH/REPLACE blocks, but this module has no runtime dependency on Aider.

Block format:
    <<<<<<< SEARCH
    original content to find
    =======
    replacement content
    >>>>>>> REPLACE
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEARCH_REPLACE_RE = re.compile(
    r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)


@dataclass
class EditBlock:
    file_path: str
    search: str
    replace: str
    reason: str = ""


@dataclass
class EditResult:
    ok: bool
    file_path: str = ""
    applied: bool = False
    error: str = ""
    preview: str = ""


def parse_edit_blocks(text: str, default_file: str = "") -> list[EditBlock]:
    """Parse SEARCH/REPLACE blocks from text."""
    blocks = []
    file_hint_re = re.compile(r"^(?:#|//|--)\s*File:\s*(.+)$", re.MULTILINE)
    current_file = default_file

    for match in _SEARCH_REPLACE_RE.finditer(text):
        prefix = text[: match.start()]
        hints = file_hint_re.findall(prefix)
        if hints:
            current_file = hints[-1].strip()

        blocks.append(
            EditBlock(
                file_path=current_file,
                search=match.group(1),
                replace=match.group(2),
            )
        )
    return blocks


def apply_edit_block(content: str, block: EditBlock) -> EditResult:
    """Validate and preview one edit block against file content."""
    if block.search not in content:
        return EditResult(
            ok=False,
            file_path=block.file_path,
            error=f"SEARCH block not found in {block.file_path}",
        )

    count = content.count(block.search)
    if count > 1:
        return EditResult(
            ok=False,
            file_path=block.file_path,
            error=f"SEARCH block matches {count} times in {block.file_path}; must be unique",
        )

    return EditResult(
        ok=True,
        file_path=block.file_path,
        applied=True,
        preview=_make_preview(block.search, block.replace),
    )


def apply_edits(content: str, blocks: list[EditBlock]) -> str:
    """Apply multiple edit blocks sequentially.

    The operation is strict: if any block is missing or non-unique at the point
    it is applied, a ValueError is raised. This prevents silent partial edits.
    """
    for block in blocks:
        result = apply_edit_block(content, block)
        if not result.ok:
            raise ValueError(result.error)
        content = content.replace(block.search, block.replace, 1)
    return content


def format_edit_block(
    file_path: str,
    search: str,
    replace: str,
    reason: str = "",
) -> str:
    """Format a SEARCH/REPLACE block for use in prompts."""
    header = f"# File: {file_path}"
    if reason:
        header += f"  (reason: {reason})"
    return (
        f"{header}\n"
        f"<<<<<<< SEARCH\n"
        f"{search}\n"
        f"=======\n"
        f"{replace}\n"
        f">>>>>>> REPLACE"
    )


def _make_preview(search: str, replace: str) -> str:
    """Generate a concise diff-style preview."""
    search_lines = search.strip().split("\n")
    replace_lines = replace.strip().split("\n")
    preview = []
    for line in search_lines[:3]:
        preview.append(f"- {line[:60]}")
    preview.append("...")
    for line in replace_lines[:3]:
        preview.append(f"+ {line[:60]}")
    if len(replace_lines) > 3:
        preview.append(f"+ ... ({len(replace_lines)} lines total)")
    return "\n".join(preview)
