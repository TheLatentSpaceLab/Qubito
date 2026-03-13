"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")
MODEL = os.getenv("MODEL")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", MODEL_PROVIDER).lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

