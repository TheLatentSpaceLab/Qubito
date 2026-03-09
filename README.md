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
- An LLM provider ([Ollama](https://ollama.com/) or [Gemini](https://aistudio.google.com/))

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
| `MODEL_PROVIDER` | `ollama` | LLM provider to use: `ollama` or `gemini` |
| `MODEL` | `qwen2:1.5b` | Model name (depends on the provider) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL (only for `ollama`) |
| `GOOGLE_API_KEY` | — | [Google AI API key](https://aistudio.google.com/apikey) (only for `gemini`) |

### 4. Set up your LLM provider

**Ollama (default)** — runs locally, no API key needed:

```bash
ollama pull qwen2:1.5b
```

**Gemini** — set these in your `.env`:

```
MODEL_PROVIDER=gemini
MODEL=gemini-2.0-flash
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

A random character will greet you. Type your messages and chat with them. Type `/exit` or `/quit` to leave.

## Project Structure

```
main.py                          # Entry point
src/
  constants.py                   # Settings loaded from .env
  display.py                     # Rich terminal UI
  agents/
    agent.py                     # Base Agent class
    agent_manager.py             # Random agent selection
    characters/
      joey.py                    # Joey Tribbiani
      monica.py                  # Monica Geller
      ross.py                    # Ross Geller
      chandler.py                # Chandler Bing
      phoebe.py                  # Phoebe Buffay
  ai/
    model_facade.py              # LLM abstraction layer
    clients/
      ollama.py                  # Ollama client
      gemini.py                  # Gemini client
```
