import json
import logging
from functools import lru_cache

import numpy as np
import requests

from src.constants import VLLM_API_KEY, VLLM_BASE_URL
from src.genai.chat_response import ChatResponse, ToolCall
from src.genai.client import AIClient

logger = logging.getLogger(__name__)


class VLLMClient(AIClient):
    """vLLM implementation using its OpenAI-compatible API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"

    def _request(self, endpoint: str, body: dict) -> dict:
        """Send a request to the vLLM server."""
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        raw = requests.post(
            url=f"{self.base_url}{endpoint}",
            headers=headers,
            data=json.dumps(body),
        )
        return raw.json()

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """Send a chat completion request to the vLLM server."""
        if not model:
            raise ValueError("Model is required.")
        if not messages:
            raise ValueError("messages cannot be empty")

        body: dict = {"model": model, "messages": messages}

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

        data = self._request("/v1/chat/completions", body)

        if "error" in data:
            logger.error("vLLM error: %s", json.dumps(data, default=str))
            msg = data["error"]
            if isinstance(msg, dict):
                msg = msg.get("message", msg)
            raise RuntimeError(f"vLLM API error: {msg}")

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> ChatResponse:
        """Parse an OpenAI-compatible response into a ChatResponse."""
        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"vLLM returned no choices: {data}")

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

    def embed(self, model: str, texts: list[str]) -> np.ndarray:
        """Generate embeddings via the vLLM embeddings endpoint."""
        data = self._request(
            "/v1/embeddings",
            {"model": model, "input": texts},
        )

        if "error" in data:
            raise RuntimeError(f"vLLM embedding error: {data['error']}")

        embeddings = [item["embedding"] for item in data["data"]]
        return np.array(embeddings, dtype=np.float32)


@lru_cache(maxsize=1)
def get_vllm_client() -> VLLMClient:
    """Return a cached vLLM client instance."""
    return VLLMClient(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)
