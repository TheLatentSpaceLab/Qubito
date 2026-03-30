"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

AI_CLIENT_PROVIDER = os.getenv("AI_CLIENT_PROVIDER")
AI_CLIENT_MODEL = os.getenv("AI_CLIENT_MODEL")
AI_CLIENT_FALLBACK_MODEL = os.getenv("AI_CLIENT_FALLBACK_MODEL", "")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", AI_CLIENT_PROVIDER).lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", "128000"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
VLLM_API_KEY = os.getenv("VLLM_API_KEY")

DEFAULT_CHARACTER = os.getenv("DEFAULT_CHARACTER", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

DAEMON_HOST = os.getenv("QUBITO_DAEMON_HOST", "127.0.0.1")
DAEMON_PORT = int(os.getenv("QUBITO_DAEMON_PORT", "8741"))

SESSION_TIMEOUT_MINUTES = int(os.getenv("QUBITO_SESSION_TIMEOUT", "30"))

AUTH_ENABLED = os.getenv("QUBITO_AUTH_ENABLED", "false").lower() == "true"
AUTH_LOCALHOST_BYPASS = os.getenv("QUBITO_AUTH_LOCALHOST_BYPASS", "true").lower() == "true"

