"""Constants updater: safely update backend constants files with new providers."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Each frozenset now lives in the module that owns it.
_SET_FILE_MAP = {
    "GFW_BACKENDS": "backends_constants.py",
    "CODE_CAPABLE_BACKENDS": "backends_constants_code_tools.py",
    "TOOL_CAPABLE_BACKENDS": "backends_constants_code_tools.py",
}

# Regex patterns for locating insertion points in constants files
_GFW_INSERT = re.compile(r"(GFW_BACKENDS = frozenset\(\{)", re.MULTILINE)
_CODE_INSERT = re.compile(r"(CODE_CAPABLE_BACKENDS = frozenset\(\{)", re.MULTILINE)
_TOOL_INSERT = re.compile(r"(TOOL_CAPABLE_BACKENDS = frozenset\(\{)", re.MULTILINE)

# Backend IDs must be simple ASCII identifiers to avoid breaking frozenset literals.
_VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_names(names: list[str]) -> list[str]:
    """Return invalid backend IDs, if any."""
    return [n for n in names if not _VALID_NAME.match(n)]


def _resolve_constants_path(file_path: str | None, set_name: str) -> Path | None:
    """Return the actual constants file for a given set name."""
    if file_path is None:
        rel_path = _SET_FILE_MAP.get(set_name)
    else:
        path = Path(file_path)
        basename = path.name
        mapped = _SET_FILE_MAP.get(set_name)
        if mapped and basename != mapped:
            logger.warning(
                "%s is stored in %s, not %s; redirecting.",
                set_name,
                mapped,
                basename,
            )
        rel_path = _SET_FILE_MAP.get(set_name, file_path)

    if rel_path is None:
        return None
    return Path(rel_path)


def generate_patch(
    constants_path: str | None = None,
    new_names: list[str] | None = None,
    gfw: bool = True,
    code: bool = True,
    tool: bool = True,
) -> str:
    """Generate a unified diff-style patch for the constants files.

    Instead of directly modifying the file, this generates the additions
    that a human or CI pipeline can apply. This is safer than auto-editing
    the production constants file.

    Returns:
        A human-readable diff showing what to add where.
    """
    if new_names is None:
        new_names = []
    invalid = _validate_names(new_names)
    if invalid:
        raise ValueError(f"Invalid backend IDs (must match {_VALID_NAME.pattern}): {invalid}")
    names_str = ", ".join(f"'{n}'" for n in new_names)

    lines = [
        "# === Auto-generated constants patch ===",
        f"# Generated for: {names_str}",
        "",
    ]

    if gfw:
        lines.append(f"# In {_SET_FILE_MAP['GFW_BACKENDS']} GFW_BACKENDS frozenset, add:")
        lines.append(f"    {names_str},")
        lines.append("")

    if code:
        lines.append(f"# In {_SET_FILE_MAP['CODE_CAPABLE_BACKENDS']} CODE_CAPABLE_BACKENDS frozenset, add:")
        lines.append(f"    {names_str},")
        lines.append("")

    if tool:
        lines.append(f"# In {_SET_FILE_MAP['TOOL_CAPABLE_BACKENDS']} TOOL_CAPABLE_BACKENDS frozenset, add:")
        lines.append(f"    {names_str},")
        lines.append("")

    return "\n".join(lines)


def apply_to_frozenset(
    set_name: str,
    new_names: list[str],
    file_path: str | None = None,
) -> bool:
    """Directly insert new names into a frozenset in the correct constants file.

    Args:
        set_name: Name of the frozenset ('GFW_BACKENDS', 'CODE_CAPABLE_BACKENDS',
            'TOOL_CAPABLE_BACKENDS').
        new_names: List of backend IDs to add.
        file_path: Optional path to the constants file. If omitted or wrong,
            the updater redirects to the module that owns the set.

    Returns:
        True if successfully applied, False otherwise.
    """
    invalid = _validate_names(new_names)
    if invalid:
        logger.error("Invalid backend IDs (must match %s): %s", _VALID_NAME.pattern, invalid)
        return False

    path = _resolve_constants_path(file_path, set_name)
    if path is None:
        logger.warning("No constants file known for set %s", set_name)
        return False

    if not path.exists():
        logger.warning("Constants file not found: %s", path)
        return False

    content = path.read_text(encoding="utf-8")

    # Find the frozenset definition
    pattern = re.compile(
        rf"({set_name}\s*=\s*frozenset\(\{{)",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        logger.warning("Set %s not found in %s", set_name, path)
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
        path,
        names_to_add,
    )
    return True
