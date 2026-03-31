"""Anthropic (Claude) implementation of the AIClient interface."""

import json
import logging
from functools import lru_cache

from anthropic import Anthropic
from anthropic.types import Message, ToolParam

from src.constants import ANTHROPIC_API_KEY
from src.genai.client import AIClient
from src.genai.chat_response import ChatResponse, ToolCall
from src.genai.clients import retry_on_transient

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 4096


class AnthropicClient(AIClient):
    """Anthropic Claude implementation of chat API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required to use Anthropic.")
        self.client = Anthropic(api_key=self.api_key)

    def _extract_system(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Separate system messages from conversation messages.

        Anthropic expects ``system`` as a top-level parameter, not as a
        message role.
        """
        system_parts: list[str] = []
        filtered: list[dict] = []

        for msg in messages:
            role = (msg.get("role") or "").strip()
            content = (msg.get("content") or "").strip()
            if role == "system":
                if content:
                    system_parts.append(content)
            else:
                filtered.append(msg)

        system = "\n\n".join(system_parts) if system_parts else None
        return system, filtered

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert internal message format to Anthropic's API format.

        Key differences from OpenAI-style messages:
        - Assistant tool-call messages use ``content`` blocks with
          ``type: tool_use`` instead of a top-level ``tool_calls`` list.
        - Tool results are sent as ``role: user`` with ``type: tool_result``
          content blocks.
        """
        converted: list[dict] = []

        for msg in messages:
            role = (msg.get("role") or "").strip()
            content = msg.get("content", "")

            # --- assistant message with tool_calls (from a previous round) ---
            if role == "assistant" and "tool_calls" in msg:
                parts: list[dict] = []
                if content:
                    parts.append({"type": "text", "text": content})
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    args = fn["arguments"]
                    parts.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": fn["name"],
                        "input": json.loads(args) if isinstance(args, str) else args,
                    })
                converted.append({"role": "assistant", "content": parts})
                continue

            # --- tool result message ---
            if role == "tool":
                tool_use_id = msg.get("tool_call_id", "")
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": str(content),
                        }
                    ],
                })
                continue

            # --- regular user / assistant messages ---
            if role in ("user", "assistant") and content:
                converted.append({"role": role, "content": content})

        return self._merge_consecutive_user(converted)

    def _merge_consecutive_user(self, messages: list[dict]) -> list[dict]:
        """Merge consecutive user messages (Anthropic rejects them otherwise)."""
        merged: list[dict] = []
        for msg in messages:
            if merged and merged[-1]["role"] == "user" and msg["role"] == "user":
                prev = merged[-1]["content"]
                curr = msg["content"]
                if isinstance(prev, str) and isinstance(curr, str):
                    merged[-1]["content"] = f"{prev}\n\n{curr}"
                else:
                    prev_list = prev if isinstance(prev, list) else [{"type": "text", "text": prev}]
                    curr_list = curr if isinstance(curr, list) else [{"type": "text", "text": curr}]
                    merged[-1]["content"] = prev_list + curr_list
            else:
                merged.append(msg)
        return merged

    def _build_tools(self, tools: list[dict]) -> list[ToolParam]:
        """Convert internal tool definitions to Anthropic ToolParam format."""
        return [
            ToolParam(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t["input_schema"],
            )
            for t in tools
        ]

    @retry_on_transient()
    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """Send a chat request to Anthropic Claude.

        Parameters
        ----------
        model : str
            Claude model identifier (e.g. ``claude-sonnet-4-20250514``).
        messages : list[dict]
            Conversation messages in internal role/content format.
        tools : list[dict] | None
            Optional tool definitions (name, description, input_schema).

        Returns
        -------
        ChatResponse
            Structured response with optional tool calls.
        """
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        system, filtered = self._extract_system(messages)
        converted = self._convert_messages(filtered)

        params: dict = {
            "model": model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": converted,
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = self._build_tools(tools)

        response: Message = self.client.messages.create(**params)
        return self._parse_response(response)

    def _parse_response(self, response: Message) -> ChatResponse:
        """Convert an Anthropic Message into a ChatResponse."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input) if block.input else {},
                    )
                )

        content = "\n".join(text_parts).strip() or None

        if tool_calls:
            return ChatResponse(content=content, tool_calls=tool_calls)
        return ChatResponse(content=content or "")


@lru_cache(maxsize=1)
def get_anthropic_client() -> AnthropicClient:
    """Return a cached Anthropic client instance."""
    return AnthropicClient()
