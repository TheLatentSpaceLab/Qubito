from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from src.agents.character_loader import CharacterData
from src.genai.chat_response import ChatResponse, ToolCall


# ---------------------------------------------------------------------------
# Filesystem fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_qubito_dir(tmp_path: Path) -> Path:
    """Create a minimal ~/.qubito-like directory tree for testing."""
    for sub in ("agents", "skills", "rules", "mcp", "memory"):
        (tmp_path / sub).mkdir()
    return tmp_path


@pytest.fixture()
def sample_agent_md(tmp_qubito_dir: Path) -> Path:
    """Write a sample character .md file and return its path."""
    p = tmp_qubito_dir / "agents" / "tester.md"
    p.write_text(
        '---\n'
        'name: "Tester"\n'
        'emoji: "🧪"\n'
        'color: "bold cyan"\n'
        'hi_message: "Hello from tests!"\n'
        'bye_message: "Bye from tests!"\n'
        'thinking: "Hmm|Processing"\n'
        '---\n\n'
        'A testing personality.\n',
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def sample_skill_md(tmp_qubito_dir: Path) -> Path:
    """Write a sample skill SKILL.md file and return its path."""
    skill_dir = tmp_qubito_dir / "skills" / "ping"
    skill_dir.mkdir(parents=True, exist_ok=True)
    p = skill_dir / "SKILL.md"
    p.write_text(
        '---\n'
        'name: "ping"\n'
        'description: "Replies with pong"\n'
        '---\n\n'
        'Ping skill instructions.\n',
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def sample_llm_skill_md(tmp_qubito_dir: Path) -> Path:
    """Write a sample LLM skill SKILL.md file and return its path."""
    skill_dir = tmp_qubito_dir / "skills" / "summarize"
    skill_dir.mkdir(parents=True, exist_ok=True)
    p = skill_dir / "SKILL.md"
    p.write_text(
        '---\n'
        'name: "summarize"\n'
        'description: "Summarizes text"\n'
        '---\n\n'
        'Summarize the following text concisely.\n',
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# Character fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_character() -> CharacterData:
    return CharacterData(
        name="Tester",
        emoji="🧪",
        color="bold cyan",
        hi_message="Hello from tests!",
        personality="A testing personality.",
        bye_message="Bye from tests!",
        thinking=("Hmm", "Processing"),
    )


# ---------------------------------------------------------------------------
# Mock AI client
# ---------------------------------------------------------------------------

class MockAIClient:
    """Fake AIClient returning pre-configured responses."""

    tool_arguments_as_dict: bool = False

    def __init__(self, responses: list[ChatResponse] | None = None) -> None:
        self.responses = list(responses or [ChatResponse(content="mock response")])
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        resp = self.responses[min(self._call_index, len(self.responses) - 1)]
        self._call_index += 1
        return resp

    def embed(self, model: str, texts: list[str]) -> Any:
        import numpy as np
        return np.random.rand(len(texts), 384).astype("float32")


@pytest.fixture()
def mock_ai_client() -> MockAIClient:
    return MockAIClient()


# ---------------------------------------------------------------------------
# Mock MCP manager
# ---------------------------------------------------------------------------

class MockMCPManager:
    """Stub MCPManager for testing tool-call flows."""

    def __init__(self, tool_results: dict[str, str] | None = None) -> None:
        self._tool_results = tool_results or {}
        self.calls: list[tuple[str, dict]] = []

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": f"Mock tool {name}",
                "input_schema": {"type": "object", "properties": {}},
            }
            for name in self._tool_results
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        self.calls.append((name, arguments))
        return self._tool_results.get(name, f"result from {name}")

    def close(self) -> None:
        pass


@pytest.fixture()
def mock_mcp_manager() -> MockMCPManager:
    return MockMCPManager(tool_results={"read_file": "file contents here"})
