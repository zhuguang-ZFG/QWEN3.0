from dataclasses import dataclass
from enum import Enum


class AuthorityClass(str, Enum):
    READ_ONLY = "read_only"
    WRITE_WORKSPACE = "write_workspace"
    NETWORK_READ = "network_read"
    NETWORK_WRITE = "network_write"
    SHELL_EXEC = "shell_exec"
    DATABASE = "database"
    DEPLOYMENT = "deployment"
    HARDWARE = "hardware"


DANGEROUS_AUTHORITIES = frozenset({
    AuthorityClass.DEPLOYMENT, AuthorityClass.HARDWARE,
    AuthorityClass.NETWORK_WRITE, AuthorityClass.SHELL_EXEC,
})


def requires_approval(authority: AuthorityClass) -> bool:
    """Authorities that need explicit task approval before execution."""
    return authority in DANGEROUS_AUTHORITIES


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    tags: tuple[str, ...] = ()
    authority: AuthorityClass = AuthorityClass.READ_ONLY
    requires_secret: bool = False
    requires_approval: bool = False
    max_args: int = 10
    timeout_sec: float = 30.0

    def __post_init__(self) -> None:
        authority = self.authority
        if not isinstance(authority, AuthorityClass):
            authority = AuthorityClass(authority)
            object.__setattr__(self, "authority", authority)
        if requires_approval(authority) and not self.requires_approval:
            object.__setattr__(self, "requires_approval", True)


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
        authority=AuthorityClass.READ_ONLY,
    ))
    registry.register(ToolDefinition(
        name="dev_search_error",
        description="Search public sources for sanitized programming errors.",
        tags=("programming", "error", "traceback", "debug", "readonly", "lima-code"),
        authority=AuthorityClass.READ_ONLY,
    ))
    registry.register(ToolDefinition(
        name="dev_read_url",
        description="Read a public HTTP or HTTPS URL for LiMa Code.",
        tags=("url", "docs", "fetch", "readonly", "lima-code"),
        authority=AuthorityClass.NETWORK_READ,
    ))
    registry.register(ToolDefinition(
        name="dev_fetch_github_file",
        description="Fetch a public GitHub file for reference.",
        tags=("github", "source", "reference", "readonly", "lima-code"),
        authority=AuthorityClass.NETWORK_READ,
    ))
    registry.register(ToolDefinition(
        name="dev_summarize_sources",
        description="Summarize source dictionaries into prompt evidence.",
        tags=("evidence", "summary", "sources", "lima-code"),
    ))
    return registry
