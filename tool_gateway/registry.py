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
