import requests
import json
from functools import lru_cache

from src.constants import OPENROUTER_API_KEY
from src.genai.client import AIClient
from src.genai.chat_response import ChatResponse, ToolCall


class OpenRouterClient(AIClient):
    """OpenRouter implementation of chat API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """
        Send a chat request to OpenRouter.

        Parameters
        ----------
        model : str
            OpenRouter model name used for generation.
        messages : list[dict]
            Message list in role/content format.
        tools : list[dict] | None
            Optional MCP tool definitions.

        Returns
        -------
        ChatResponse
            Structured response with optional tool calls.
        """
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        body: dict = {
            "model": model,
            "messages": messages,
        }

        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ]

        raw = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(body),
        )

        data = raw.json()

        if "error" in data:
            error = data["error"]
            msg = error.get("message", error) if isinstance(error, dict) else error
            raise RuntimeError(f"OpenRouter API error: {msg}")

        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {data}")

        message = choices[0]["message"]

        content = message.get("content")
        tool_calls: list[ToolCall] = []

        for tc in message.get("tool_calls") or []:
            args = tc["function"]["arguments"]
            tool_calls.append(
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(args) if isinstance(args, str) else args,
                )
            )

        return ChatResponse(content=content, tool_calls=tool_calls)


@lru_cache(maxsize=1)
def get_openrouter_client() -> OpenRouterClient:
    """
    Return a cached OpenRouter client instance.

    Returns
    -------
    OpenRouterClient
        Singleton-like cached client configured from app constants.
    """
    return OpenRouterClient(api_key=OPENROUTER_API_KEY)
