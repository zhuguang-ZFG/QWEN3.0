from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    tags: tuple[str, ...] = ()
    requires_secret: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def search(self, query: str, limit: int = 5) -> list[ToolDefinition]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, ToolDefinition]] = []
        for tool in self._tools.values():
            haystack = " ".join([tool.name, tool.description, *tool.tags]).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, tool))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [tool for _score, tool in scored[:limit]]


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="dev_search_docs",
        description="Search public programming documentation for LiMa Code.",
        tags=("programming", "docs", "search", "readonly", "lima-code"),
    ))
    registry.register(ToolDefinition(
        name="dev_search_error",
        description="Search public sources for sanitized programming errors.",
        tags=("programming", "error", "traceback", "debug", "readonly", "lima-code"),
    ))
    registry.register(ToolDefinition(
        name="dev_read_url",
        description="Read a public HTTP or HTTPS URL for LiMa Code.",
        tags=("url", "docs", "fetch", "readonly", "lima-code"),
    ))
    registry.register(ToolDefinition(
        name="dev_fetch_github_file",
        description="Fetch a public GitHub file for reference.",
        tags=("github", "source", "reference", "readonly", "lima-code"),
    ))
    registry.register(ToolDefinition(
        name="dev_summarize_sources",
        description="Summarize source dictionaries into prompt evidence.",
        tags=("evidence", "summary", "sources", "lima-code"),
    ))
    return registry
