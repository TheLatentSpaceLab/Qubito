# Friends TV Show Bot
![](https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3aW52dmg0M3prdjhxODVnaGxncjZ5aG81dXl3OTl3N2xyNjN4bWg0MyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Rhf0uSWt1P2TFqVMZK/giphy.gif)

A terminal chatbot where you talk to characters from the TV show Friends. Each character has their own personality, catchphrases, and style.
<img width="1908" height="662" alt="image" src="https://github.com/user-attachments/assets/a3a85586-0864-4c07-bdb2-8eb68ea73782" />


## Characters

| Emoji | Character | Personality |
|-------|-----------|-------------|
| 🍕 | Joey Tribbiani | Food-loving, loyal, "How you doin'?" |
| 🍳 | Monica Geller | Competitive, organized, amazing cook |
| 🦕 | Ross Geller | Paleontologist, intellectual, "We were on a break!" |
| 😏 | Chandler Bing | Sarcastic, "Could this BE any more..." |
| 🎸 | Phoebe Buffay | Quirky, free-spirited, "Smelly Cat" musician |

## Setup Guide

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An LLM provider ([Ollama](https://ollama.com/), [Gemini](https://aistudio.google.com/), or [OpenRouter](https://openrouter.ai/))

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

Copy the example file and edit it:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_CLIENT_PROVIDER` | `ollama` | LLM provider: `ollama`, `gemini`, or `openrouter` |
| `AI_CLIENT_MODEL` | `cogito:3b` | Model name (depends on the provider) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL (only for `ollama`) |
| `EMBEDDING_PROVIDER` | `AI_CLIENT_PROVIDER` | Embedding backend: `ollama` or `gemini` |
| `EMBEDDING_MODEL` | provider default | Embedding model (e.g. `nomic-embed-text` or `text-embedding-004`) |
| `GOOGLE_API_KEY` | — | [Google AI API key](https://aistudio.google.com/apikey) (only for `gemini`) |
| `OPENROUTER_API_KEY` | — | [OpenRouter API key](https://openrouter.ai/) (only for `openrouter`) |

### 4. Set up your LLM provider

**Ollama (default)** — runs locally, no API key needed:

```bash
ollama pull qwen2:1.5b
ollama pull nomic-embed-text
```

**Gemini** — set these in your `.env`:

```
AI_CLIENT_PROVIDER=gemini
MODEL=gemini-2.0-flash
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=text-embedding-004
GOOGLE_API_KEY=your-api-key-here
```

### 5. (Optional) Create a shell alias

Add this to your `~/.bashrc` or `~/.zshrc` for quick access:

```bash
alias friends='cd ~/my/friends-bot && uv run python main.py'
```

Then reload your shell:

```bash
source ~/.bashrc
```

## Usage

```bash
uv run python main.py
```

A random character will greet you. Type your messages and chat with them. Type `q`, `/exit`, or `/quit` to leave.

Commands:
- `/load <path>` — index a local text file for retrieval context
- `/context` or `/ctx` — inspect currently indexed chunks
- `/history` — print chat history
- `/lineup` — show available characters
- `/summarize` — summarize the conversation so far
- `/help` — list available commands

## Project Structure

```
main.py                          # Entry point
agents/                          # Character definitions (markdown)
rules/                           # Behavior rules (markdown)
skills/                          # Slash command definitions (markdown)
mcp_servers.json                 # MCP server configs
src/
  constants.py                   # Settings loaded from .env
  display.py                     # Rich terminal UI
  agents/
    agent.py                     # Agent class
    agent_manager.py             # Random agent selection
    character_loader.py          # Load characters from markdown
  genai/
    model_facade.py              # LLM abstraction with tool-use loop
    clients/
      ollama.py                  # Ollama client
      gemini.py                  # Gemini client
      openrouter.py              # OpenRouter client
  mcp/
    manager.py                   # MCP tool integration
  rag/
    faiss_store.py               # FAISS document store
  rules/
    rule_loader.py               # Load rules from markdown
  skills/
    skill_loader.py              # Load skills from markdown
    registry.py                  # Skill dispatch
    handlers.py                  # Built-in skill handlers
  ocr/
    reader.py                    # OCR (FasterRCNN + TrOCR)
```
