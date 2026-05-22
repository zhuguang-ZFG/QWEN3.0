"""Entity Extraction — LightRAG-inspired code entity extraction from requests.

Extracts structured entities from user messages:
- File paths (server.py, routing_engine.py)
- Function/class names (def route, class Pipeline)
- Module references (context_pipeline, session_memory)
- Error patterns (TypeError, ImportError)
- Technology keywords (FastAPI, asyncio, SQLite)

Extracted entities drive graph-aware retrieval for precise context injection.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ExtractedEntities:
    """Structured entities extracted from a request."""

    file_paths: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)

    @property
    def total_entities(self) -> int:
        return (len(self.file_paths) + len(self.functions) + len(self.classes)
                + len(self.modules) + len(self.errors) + len(self.technologies))

    def to_query_terms(self) -> list[str]:
        """Convert entities to search query terms for retrieval."""
        terms = []
        terms.extend(self.file_paths)
        terms.extend(self.functions)
        terms.extend(self.classes)
        terms.extend(self.modules)
        return terms[:10]


_FILE_PATTERN = re.compile(r'\b[\w/\\]+\.\w{1,4}\b')
_FUNC_PATTERN = re.compile(r'\b(?:def|function|func)\s+(\w+)')
_CLASS_PATTERN = re.compile(r'\b(?:class|struct|interface)\s+(\w+)')
_ERROR_PATTERN = re.compile(r'\b(\w*(?:Error|Exception|Fault))\b')
_MODULE_PATTERN = re.compile(r'\b(?:import|from|require)\s+["\']?([\w.]+)')

TECH_KEYWORDS = {
    "fastapi", "flask", "django", "express", "react", "vue",
    "asyncio", "sqlite", "postgres", "redis", "docker",
    "kubernetes", "nginx", "pytorch", "tensorflow", "numpy",
}


def extract_entities(messages: list[dict]) -> ExtractedEntities:
    """Extract code entities from user messages."""
    text = _get_user_text(messages)
    if not text:
        return ExtractedEntities()

    entities = ExtractedEntities()

    # File paths
    entities.file_paths = list(set(_FILE_PATTERN.findall(text)))[:10]

    # Functions
    entities.functions = list(set(_FUNC_PATTERN.findall(text)))[:10]

    # Classes
    entities.classes = list(set(_CLASS_PATTERN.findall(text)))[:10]

    # Modules
    entities.modules = list(set(_MODULE_PATTERN.findall(text)))[:10]

    # Errors
    entities.errors = list(set(_ERROR_PATTERN.findall(text)))[:5]

    # Technologies
    words = set(text.lower().split())
    entities.technologies = list(words & TECH_KEYWORDS)[:5]

    return entities


def _get_user_text(messages: list[dict]) -> str:
    """Extract all user text from messages."""
    parts = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
    return " ".join(parts)
