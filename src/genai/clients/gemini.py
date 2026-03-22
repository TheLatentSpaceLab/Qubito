import json
from functools import lru_cache
import os

import numpy as np

from src.genai import AIClient
from src.genai.chat_response import ChatResponse, ToolCall


class GeminiClient(AIClient):
    """Gemini implementation of chat and embedding APIs."""

    def __init__(self, api_key: str | None = None):
        """
        Create a Gemini client wrapper.

        Parameters
        ----------
        api_key : str | None, optional
            Google API key. If omitted, ``GOOGLE_API_KEY`` is used.

        Returns
        -------
        None
            Initializes the underlying Gemini SDK client.
        """
        from google import genai

        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required to use Gemini.")

        self.genai = genai
        self.client = genai.Client(api_key=self.api_key)

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """
        Send a chat request to Gemini.

        Parameters
        ----------
        model : str
            Gemini model name used for generation.
        messages : list[dict]
            Message list in role/content format.
        tools : list[dict] | None
            Optional MCP tool definitions.

        Returns
        -------
        ChatResponse
            Structured response with optional tool calls.
        """
        if not messages:
            raise ValueError("messages cannot be empty")

        system_instruction = None
        contents = []

        for message in messages:
            role = (message.get("role") or "").strip()
            content = (message.get("content") or "").strip()

            # --- assistant message with tool_calls (from a previous round) ---
            if role == "assistant" and "tool_calls" in message:
                parts = []
                for tc in message["tool_calls"]:
                    fn = tc["function"]
                    args = fn["arguments"]
                    parts.append(
                        self.genai.types.Part(
                            function_call=self.genai.types.FunctionCall(
                                name=fn["name"],
                                args=json.loads(args) if isinstance(args, str) else args,
                            )
                        )
                    )
                contents.append(self.genai.types.Content(role="model", parts=parts))
                continue

            # --- tool result message ---
            if role == "tool":
                tool_name = message.get("name", "unknown")
                contents.append(
                    self.genai.types.Content(
                        role="user",
                        parts=[
                            self.genai.types.Part(
                                function_response=self.genai.types.FunctionResponse(
                                    name=tool_name,
                                    response={"result": content},
                                )
                            )
                        ],
                    )
                )
                continue

            # --- system messages → aggregated system_instruction ---
            if role == "system":
                if content:
                    if system_instruction is None:
                        system_instruction = content
                    else:
                        system_instruction += f"\n\n{content}"
                continue

            if not content:
                continue

            mapped_role = "model" if role == "assistant" else "user"
            contents.append(
                self.genai.types.Content(
                    role=mapped_role,
                    parts=[self.genai.types.Part(text=content)]
                )
            )

        if not contents:
            raise ValueError("No user/assistant content found in messages.")

        config_kwargs: dict = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        if tools:
            config_kwargs["tools"] = [
                {
                    "function_declarations": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["input_schema"],
                        }
                        for t in tools
                    ]
                }
            ]

        config = (
            self.genai.types.GenerateContentConfig(**config_kwargs)
            if config_kwargs
            else None
        )

        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )

        # Check for function calls in response
        tool_calls: list[ToolCall] = []
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts or []):
                fc = getattr(part, "function_call", None)
                if fc:
                    tool_calls.append(
                        ToolCall(
                            id=f"call_{fc.name}_{id(fc)}",
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        )
                    )

        if tool_calls:
            return ChatResponse(content=None, tool_calls=tool_calls)

        # Extract text response
        text = (response.text or "").strip()
        if text:
            return ChatResponse(content=text)

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            candidate_content = getattr(candidate, "content", None)
            parts = getattr(candidate_content, "parts", None) or []
            joined = "".join(
                part.text for part in parts
                if getattr(part, "text", None)
            ).strip()
            if joined:
                return ChatResponse(content=joined)

        return ChatResponse(content="")

    def embed(self, model: str, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings through Gemini.

        Parameters
        ----------
        model : str
            Gemini embedding model name.
        texts : list[str]
            Input texts to embed.

        Returns
        -------
        numpy.ndarray
            Embedding matrix with shape ``(len(texts), embedding_dim)``.
        """
        if not model:
            raise ValueError("Embedding model is required.")
        if not texts:
            raise ValueError("texts cannot be empty")

        response = self.client.models.embed_content(
            model=model,
            contents=texts,
        )
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if not embeddings:
            raise ValueError("Invalid Gemini embedding response: missing embeddings field.")

        vectors: list[list[float]] = []
        for emb in embeddings:
            values = getattr(emb, "values", None)
            if values is None and isinstance(emb, dict):
                values = emb.get("values")
            if values is None:
                raise ValueError("Invalid Gemini embedding response: missing values field.")
            vectors.append(list(values))

        return np.asarray(vectors, dtype=np.float32)

@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    """
    Return a cached Gemini client instance.

    Returns
    -------
    GeminiClient
        Singleton-like cached client configured from environment variables.
    """
    return GeminiClient()
