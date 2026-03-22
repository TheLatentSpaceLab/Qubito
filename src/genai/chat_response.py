from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    """Structured response from a chat completion that may include tool calls."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
