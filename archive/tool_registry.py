from typing import Any, Callable


class ToolRegistry:
    """Aggregates and registers tools per agent persona."""

    def __init__(self):
        self._registry: dict[str, list[Callable]] = {}

    def register(self, agent_name: str, tool_func: Callable):
        if agent_name not in self._registry:
            self._registry[agent_name] = []
        self._registry[agent_name].append(tool_func)

    def get_tools(self, agent_name: str) -> list[Callable]:
        return self._registry.get(agent_name, [])


tool_registry = ToolRegistry()
