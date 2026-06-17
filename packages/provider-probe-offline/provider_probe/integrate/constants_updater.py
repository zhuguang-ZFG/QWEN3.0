"""Constants updater: safely update backends_constants.py with new providers."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Regex patterns for locating insertion points in backends_constants.py
_GFW_INSERT = re.compile(r"(GFW_BACKENDS = frozenset\(\{)", re.MULTILINE)
_CODE_INSERT = re.compile(r"(CODE_CAPABLE_BACKENDS = frozenset\(\{)", re.MULTILINE)
_TOOL_INSERT = re.compile(r"(TOOL_CAPABLE_BACKENDS = frozenset\(\{)", re.MULTILINE)


def generate_patch(
    constants_path: str,
    new_names: list[str],
    gfw: bool = True,
    code: bool = True,
    tool: bool = True,
) -> str:
    """Generate a unified diff-style patch for backends_constants.py.

    Instead of directly modifying the file, this generates the additions
    that a human or CI pipeline can apply. This is safer than auto-editing
    the production constants file.

    Returns:
        A human-readable diff showing what to add where.
    """
    names_str = ", ".join(f"'{n}'" for n in new_names)

    lines = [
        "# === Auto-generated constants patch ===",
        f"# Generated for: {names_str}",
        "",
    ]

    if gfw:
        lines.append("# In GFW_BACKENDS frozenset, add:")
        lines.append(f"    {names_str},")
        lines.append("")

    if code:
        lines.append("# In CODE_CAPABLE_BACKENDS frozenset, add:")
        lines.append(f"    {names_str},")
        lines.append("")

    if tool:
        lines.append("# In TOOL_CAPABLE_BACKENDS frozenset, add:")
        lines.append(f"    {names_str},")
        lines.append("")

    return "\n".join(lines)


def apply_to_frozenset(file_path: str, set_name: str, new_names: list[str]) -> bool:
    """Directly insert new names into a frozenset in backends_constants.py.

    Args:
        file_path: Path to backends_constants.py
        set_name: Name of the frozenset ('GFW_BACKENDS', 'CODE_CAPABLE_BACKENDS', 'TOOL_CAPABLE_BACKENDS')
        new_names: List of backend IDs to add

    Returns:
        True if successfully applied, False otherwise.
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning("Constants file not found: %s", file_path)
        return False

    content = path.read_text(encoding="utf-8")

    # Find the frozenset definition
    pattern = re.compile(
        rf"({set_name}\s*=\s*frozenset\(\{{)",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        logger.warning("Set %s not found in %s", set_name, file_path)
        return False

    # Find a good insertion point — after the opening brace
    insert_pos = match.end()

    # Check which names are already present
    existing = set()
    for name in new_names:
        if f"'{name}'" in content or f'"{name}"' in content:
            existing.add(name)

    names_to_add = [n for n in new_names if n not in existing]
    if not names_to_add:
        logger.info("All names already present in %s", set_name)
        return True

    # Build insertion string
    names_str = ", ".join(f"'{n}'" for n in names_to_add)
    insertion = f"\n    {names_str},"

    new_content = content[:insert_pos] + insertion + content[insert_pos:]
    path.write_text(new_content, encoding="utf-8")

    logger.info(
        "Added %d names to %s in %s: %s",
        len(names_to_add),
        set_name,
        file_path,
        names_to_add,
    )
    return True
