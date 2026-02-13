"""
SpeakNode Tool Registry
========================
데코레이터 기반 Tool 자동 등록 시스템.
새로운 Tool을 추가할 때 기존 코드를 수정할 필요 없이
@register_tool 데코레이터만 붙이면 자동으로 등록됩니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class ToolInfo:
    """등록된 Tool의 메타데이터"""
    name: str
    description: str
    handler: Callable[..., str]


class ToolRegistry:
    """
    Tool 등록소. 데코레이터로 등록된 Tool을 이름으로 디스패치합니다.

    사용법:
        registry = ToolRegistry()

        @registry.register("my_tool", "설명")
        def my_tool(args, db, rag):
            return "결과"

        result = registry.execute("my_tool", {...}, db, rag)
    """

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}

    def register(self, name: str, description: str) -> Callable:
        """
        Tool 등록 데코레이터.

        @registry.register("tool_name", "이 도구의 설명")
        def tool_name(args: dict, db, rag) -> str:
            ...
        """
        def decorator(fn: Callable[..., str]) -> Callable[..., str]:
            self._tools[name] = ToolInfo(
                name=name,
                description=description,
                handler=fn,
            )
            return fn
        return decorator

    def execute(self, name: str, args: dict, db: Any, rag: Any) -> str:
        """등록된 Tool을 이름으로 찾아 실행합니다."""
        tool = self._tools.get(name)
        if tool is None:
            return f"알 수 없는 도구: {name}"
        try:
            return tool.handler(args, db, rag)
        except Exception as e:
            return f"도구 실행 오류 ({name}): {e}"

    def get_descriptions(self) -> str:
        """LLM Router 프롬프트에 주입할 Tool 설명 문자열을 자동 생성합니다."""
        lines = ["Available tools:"]
        for i, (name, info) in enumerate(self._tools.items(), 1):
            lines.append(f"{i}. {name} - {info.description}")
        return "\n".join(lines)

    def list_tools(self) -> list[str]:
        """등록된 Tool 이름 목록"""
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# 전역 레지스트리 인스턴스 (모듈 로드 시 Tool 자동 수집용)
default_registry = ToolRegistry()
