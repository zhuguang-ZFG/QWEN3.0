from .registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, name: str, args: dict) -> dict:
        tool = self._registry.get(name)
        if not tool:
            return {"ok": False, "error": "tool_not_registered"}
        return {"ok": False, "error": "executor_not_implemented", "tool": tool.name}
