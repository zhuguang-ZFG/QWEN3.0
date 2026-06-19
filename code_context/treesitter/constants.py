from __future__ import annotations

from pathlib import Path

_EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

_TS_NODE_KINDS: dict[str, str] = {
    "class_definition": "class",
    "function_definition": "function",
    "async_function_definition": "function",
    "decorated_definition": "function",
    "method_definition": "method",
    "arrow_function": "function",
    "function_declaration": "function",
    "class_declaration": "class",
    "interface_declaration": "class",
    "type_alias_declaration": "class",
    "export_statement": "function",
}

_TS_CALLABLE_KINDS = frozenset(
    {
        "function",
        "method",
        "arrow_function",
    }
)

_TS_IMPORT_NODE_TYPES = frozenset(
    {
        "import_statement",
        "import_declaration",
        "import_from_statement",
        "import_specifier",
        "import_alias",
        "required_import",
        "package_clause",
    }
)

_TS_EXTENDS_TYPES = frozenset(
    {
        "class_heritage",
        "superclass",
        "base_class",
    }
)


def _detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    return _EXT_MAP.get(suffix, "")
