"""Anthropic (Claude) implementation of the AIClient interface."""

import json
import logging
from functools import lru_cache

from anthropic import Anthropic
from anthropic.types import Message, ToolParam, TextBlockParam

from src.constants import ANTHROPIC_API_KEY
from src.genai.client import AIClient
from src.genai.chat_response import ChatResponse, ToolCall
from src.genai.clients import retry_on_transient

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 4096
CACHE_BREAKPOINT = {"type": "ephemeral"}


class AnthropicClient(AIClient):
    """Anthropic Claude implementation of chat API with prompt caching."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required to use Anthropic.")
        self.client = Anthropic(api_key=self.api_key)

    def _extract_system(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Separate system messages from conversation messages."""
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

    def _build_cached_system(self, text: str) -> list[TextBlockParam]:
        """Wrap system text in a cacheable content block list.

        The system prompt is identical on every turn, so caching it
        avoids re-processing those tokens (90% cheaper on cache hits).
        """
        return [TextBlockParam(
            type="text",
            text=text,
            cache_control=CACHE_BREAKPOINT,
        )]

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert internal message format to Anthropic's API format."""
        converted: list[dict] = []

        for msg in messages:
            role = (msg.get("role") or "").strip()
            content = msg.get("content", "")

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

            if role in ("user", "assistant") and content:
                converted.append({"role": role, "content": content})

        return self._merge_consecutive_user(converted)

    def _inject_history_cache_breakpoint(self, messages: list[dict]) -> list[dict]:
        """Place a cache breakpoint on the last message before the final user turn.

        This caches the conversation history prefix so only the new user
        message is processed as uncached input on each turn.
        """
        if len(messages) < 2:
            return messages

        target_idx = len(messages) - 2
        target = messages[target_idx]
        content = target.get("content", "")

        if isinstance(content, str) and content:
            messages[target_idx] = {
                **target,
                "content": [
                    {"type": "text", "text": content, "cache_control": CACHE_BREAKPOINT},
                ],
            }
        elif isinstance(content, list) and content:
            last_block = {**content[-1], "cache_control": CACHE_BREAKPOINT}
            messages[target_idx] = {
                **target,
                "content": content[:-1] + [last_block],
            }

        return messages

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
        """Convert tool definitions to Anthropic ToolParam format.

        Places a cache breakpoint on the last tool so the entire tool
        list is cached as a prefix block.
        """
        result = [
            ToolParam(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t["input_schema"],
            )
            for t in tools
        ]
        if result:
            result[-1]["cache_control"] = CACHE_BREAKPOINT
        return result

    @retry_on_transient()
    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        system, filtered = self._extract_system(messages)
        converted = self._convert_messages(filtered)
        converted = self._inject_history_cache_breakpoint(converted)

        params: dict = {
            "model": model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": converted,
        }
        if system:
            params["system"] = self._build_cached_system(system)
        if tools:
            params["tools"] = self._build_tools(tools)

        response: Message = self.client.messages.create(**params)
        self._log_cache_stats(response)
        return self._parse_response(response)

    def _log_cache_stats(self, response: Message) -> None:
        """Log cache hit/miss stats for observability."""
        usage = response.usage
        created = getattr(usage, "cache_creation_input_tokens", 0) or 0
        read = getattr(usage, "cache_read_input_tokens", 0) or 0
        if created or read:
            logger.debug(
                "Anthropic cache: read=%d created=%d uncached=%d",
                read, created, usage.input_tokens,
            )

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
