from dataclasses import dataclass, field
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ToolAdapter(Protocol):
    name: str

    def execute(self, request: ToolRequest) -> ToolResult:
        raise NotImplementedError


class ToolEngine:
    def __init__(self) -> None:
        self._adapters: Dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def can_execute(self, tool_name: str) -> bool:
        return tool_name in self._adapters

    def execute(self, request: ToolRequest) -> ToolResult:
        if request.tool_name not in self._adapters:
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error=f"Tool not registered: {request.tool_name}",
            )
        return self._adapters[request.tool_name].execute(request)


class StaticKnowledgeAdapter:
    name = "knowledge_base"

    def __init__(self, knowledge: Dict[str, Any] | None = None) -> None:
        self.knowledge = knowledge or {}

    def execute(self, request: ToolRequest) -> ToolResult:
        key = str(request.payload.get("key", ""))
        if key not in self.knowledge:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Knowledge key not found: {key}",
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            evidence={key: self.knowledge[key]},
        )
