# Decorator-based tool registry for the SpeakNode agent.

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class ToolInfo:
    name: str
    description: str
    handler: Callable[..., str]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}

    def register(self, name: str, description: str) -> Callable:
        def decorator(fn: Callable[..., str]) -> Callable[..., str]:
            self._tools[name] = ToolInfo(
                name=name,
                description=description,
                handler=fn,
            )
            return fn
        return decorator

    def execute(self, name: str, args: dict, db: Any, rag: Any) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"알 수 없는 도구: {name}"
        try:
            return tool.handler(args, db, rag)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).exception("Tool '%s' 실행 중 오류", name)
            return f"도구 실행 오류 ({name}): {e}"

    def get_descriptions(self) -> str:
        """Build a tool description string for the LLM router prompt."""
        lines = ["Available tools:"]
        for i, (name, info) in enumerate(self._tools.items(), 1):
            lines.append(f"{i}. {name} - {info.description}")
        return "\n".join(lines)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# Global registry instance
default_registry = ToolRegistry()
