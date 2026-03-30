import json
import logging
import time
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

from src.constants import AI_CLIENT_FALLBACK_MODEL, OPENROUTER_API_KEY
from src.genai.client import AIClient
from src.genai.chat_response import ChatResponse, ToolCall

RETRY_DELAY_S = 2


class OpenRouterClient(AIClient):
    """OpenRouter implementation of chat API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _request(self, body: dict) -> dict:
        """Send a single request to the OpenRouter API."""
        raw = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(body),
            timeout=60,
        )
        return raw.json()

    def _parse_response(self, data: dict) -> ChatResponse:
        """Parse an OpenRouter response into a ChatResponse."""
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

    def _is_rate_limit(self, data: dict) -> bool:
        """Check if the response is a rate-limit error."""
        error = data.get("error")
        if not error:
            return False
        code = error.get("code") if isinstance(error, dict) else None
        return code == 429

    def _build_fallback_chain(self, model: str) -> list[str]:
        """Build ordered list of models to try: primary, env fallbacks."""
        chain = [model]
        if AI_CLIENT_FALLBACK_MODEL:
            for m in AI_CLIENT_FALLBACK_MODEL.split(","):
                m = m.strip()
                if m and m not in chain:
                    chain.append(m)
        return chain

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """Send a chat request, cycling through fallback models on rate-limit."""
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

        chain = self._build_fallback_chain(model)
        last_error = ""

        for i, candidate in enumerate(chain):
            body["model"] = candidate
            data = self._request(body)

            if not self._is_rate_limit(data):
                if "error" in data:
                    logger.error("OpenRouter error: %s", json.dumps(data, default=str))
                    error = data["error"]
                    msg = error.get("message", error) if isinstance(error, dict) else error
                    raise RuntimeError(f"OpenRouter API error: {msg}")
                if i > 0:
                    logger.info("Fallback '%s' responded successfully", candidate)
                return self._parse_response(data)

            raw_meta = data["error"].get("metadata", {}).get("raw", "")
            logger.warning("Rate-limited on '%s' (%s)", candidate, raw_meta)
            last_error = raw_meta

            # Wait before trying the next model
            if i < len(chain) - 1:
                time.sleep(RETRY_DELAY_S)

        tried = ", ".join(chain)
        raise RuntimeError(f"All models rate-limited: {tried}")


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
