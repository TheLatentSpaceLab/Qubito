from enum import StrEnum


class Provider(StrEnum):
    """Supported AI providers."""

    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPEN_ROUTER = "openrouter"
