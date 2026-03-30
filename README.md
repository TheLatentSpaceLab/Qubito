# Qubito

A natural-language OS that runs as a background loop, executing commands through conversation. Search the web, run code, manage files, answer messages, create calendar events, and more — all through natural language, powered by LLM agents with configurable personalities.

<img src='docs/architecture.png'>

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An LLM provider ([Ollama](https://ollama.com/), [Gemini](https://aistudio.google.com/), [OpenRouter](https://openrouter.ai/), or [vLLM](https://docs.vllm.ai/))

### Install

```bash
uv sync
```

Optional extras:

```bash
uv sync --extra discord   # Discord bot support
uv sync --extra stt       # Speech-to-text (faster-whisper)
uv sync --extra ocr       # Image OCR (torch + TrOCR)
uv sync --extra dev       # pytest for development
```

### Configure environment

```bash
cp .env.example .env
# Edit .env with your provider keys and preferences
```

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_CLIENT_PROVIDER` | — | LLM provider: `ollama`, `gemini`, or `openrouter` |
| `AI_CLIENT_MODEL` | — | Model name (depends on the provider) |
| `AI_CLIENT_FALLBACK_MODEL` | — | Comma-separated fallback models (OpenRouter only) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `EMBEDDING_PROVIDER` | same as `AI_CLIENT_PROVIDER` | Embedding backend: `ollama` or `gemini` |
| `EMBEDDING_MODEL` | provider default | e.g. `nomic-embed-text` or `text-embedding-004` |
| `CONTEXT_WINDOW` | `128000` | Max context window in tokens |
| `GOOGLE_API_KEY` | — | Google AI API key (for `gemini`) |
| `OPENROUTER_API_KEY` | — | OpenRouter API key (for `openrouter`) |
| `DEFAULT_CHARACTER` | random | Character filename without `.md` |

## Quick Start

```bash
# 1. Start the daemon (runs in background)
uv run qubito daemon start

# 2. Chat in the terminal
uv run qubito chat

# 3. Open the web UI
#    Visit http://127.0.0.1:8741/chat for standalone chat
#    Visit http://127.0.0.1:8741/ui/  for the control dashboard
```

## Commands

```bash
qubito chat                      # Interactive terminal chat
qubito chat -c joey              # Chat with a specific character
qubito chat --pick               # Pick a character interactively

qubito daemon start              # Start daemon in background
qubito daemon start --foreground # Run in foreground (for systemd)
qubito daemon stop               # Graceful shutdown
qubito daemon status             # Check if running
qubito daemon install            # Install as systemd user service
qubito daemon uninstall          # Remove systemd service

qubito telegram                  # Run the Telegram bot
qubito discord                   # Run the Discord bot

qubito auth create-token --name mobile          # Create API token
qubito auth create-token --name ci --scopes read  # Token with limited scopes
qubito auth list-tokens                          # List all tokens
qubito auth revoke-token --name mobile           # Revoke a token

qubito init                      # Scaffold ~/.qubito/ directories
qubito new-project [path]        # Create .qubito/ in a project
```

> **Note:** `chat`, `telegram`, and `discord` all require the daemon to be running first.

## Daemon

Qubito runs as a persistent background process with an HTTP API. All interfaces (CLI, Telegram, Discord, WebChat) connect through it.

### Daemon settings

| Variable | Default | Description |
|----------|---------|-------------|
| `QUBITO_DAEMON_HOST` | `127.0.0.1` | Bind address |
| `QUBITO_DAEMON_PORT` | `8741` | Bind port |
| `QUBITO_SESSION_TIMEOUT` | `30` | Minutes before idle sessions are evicted |
| `QUBITO_AUTH_ENABLED` | `false` | Enable Bearer token authentication |
| `QUBITO_AUTH_LOCALHOST_BYPASS` | `true` | Allow localhost without token when auth is on |

### systemd service

Auto-restart on crash with a 5-second delay:

```bash
qubito daemon install    # Writes ~/.config/systemd/user/qubito.service
systemctl --user start qubito
systemctl --user status qubito
journalctl --user -u qubito -f   # Follow logs

qubito daemon uninstall  # Disable and remove
```

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/status` | Health, session count, uptime, provider info |
| `GET` | `/characters` | List available characters |
| **Sessions** | | |
| `GET` | `/sessions` | List active sessions |
| `POST` | `/sessions` | Create session `{"character": "joey", "agent_id": "work"}` |
| `DELETE` | `/sessions/{id}` | Close a session |
| `GET` | `/sessions/{id}/history` | Conversation history |
| **Messaging** | | |
| `POST` | `/message` | Send message `{"session_id": "...", "message": "..."}` |
| `POST` | `/message/stream` | SSE streaming with tool call progress |
| `POST` | `/push` | Push message to channel `{"channel_target": "telegram:123", "message": "..."}` |
| **Cron** | | |
| `GET` | `/cron` | List scheduled jobs |
| `POST` | `/cron` | Create a job |
| `DELETE` | `/cron/{id}` | Remove a job |
| `PATCH` | `/cron/{id}` | Enable/disable `{"enabled": false}` |
| `POST` | `/cron/{id}/run` | Trigger immediately |
| **Webhooks** | | |
| `POST` | `/webhooks/{id}` | Receive webhook (HMAC verified) |
| **Background Tasks** | | |
| `POST` | `/tasks` | Submit `{"description": "research X", "character": "joey"}` |
| `GET` | `/tasks` | List all tasks |
| `GET` | `/tasks/{id}` | Task status and result |
| `DELETE` | `/tasks/{id}` | Cancel a task |
| **Agents** | | |
| `GET` | `/agents` | List registered agents |
| `POST` | `/agents` | Register agent config |
| `GET` | `/agents/{id}` | Get agent info |
| `DELETE` | `/agents/{id}` | Remove agent |
| **Routes** | | |
| `GET` | `/routes` | List routing rules |
| `POST` | `/routes` | Create routing rule |
| `DELETE` | `/routes/{id}` | Remove routing rule |
| **Web UI** | | |
| `GET` | `/ui/` | Dashboard |
| `GET` | `/ui/chat` | Chat interface |
| `GET` | `/ui/config` | Configuration manager |
| `GET` | `/ui/logs` | Logs viewer |
| `GET` | `/chat` | Standalone WebChat |

### Conversation persistence

Chat history is stored in SQLite at `~/.qubito/qubito.db`. Sessions and messages survive daemon restarts. When a session is recreated, the agent loads its previous conversation from the database.

### Authentication

When `QUBITO_AUTH_ENABLED=true`, all API requests (except `/status`) require a Bearer token:

```bash
# Create a token
qubito auth create-token --name my-app
# Output: qbt_abc123... (save this)

# Use it
curl -H "Authorization: Bearer qbt_abc123..." http://127.0.0.1:8741/sessions
```

Localhost connections bypass auth by default (`QUBITO_AUTH_LOCALHOST_BYPASS=true`).

## Channels

All channels implement the `Channel` interface and connect to the daemon via HTTP.

### CLI

The default interface. Supports streaming responses with tool call progress, character switching (`/agent <name>`), and shell commands (`!command`).

### Telegram

```bash
# Set in .env
TELEGRAM_BOT_TOKEN=your-bot-token

qubito telegram
```

Commands: `/start` (greet), `/change` (switch character). Supports voice messages (requires `stt` extra).

### Discord

```bash
# Set in .env
DISCORD_BOT_TOKEN=your-bot-token

# Install the extra
uv sync --extra discord
qubito discord
```

Commands: `/change` (switch character). Messages split at 2000 chars.

### WebChat

No setup needed — available at `http://127.0.0.1:8741/chat` when the daemon is running. Character picker, SSE streaming, tool call progress.

## Slash Commands

Type these in any chat interface:

| Command | Description |
|---------|-------------|
| `/load <path>` | Index a file (PDF, text, image) for RAG retrieval |
| `/context` | Inspect indexed chunks |
| `/history` | Print conversation history |
| `/lineup` | Show model configuration |
| `/model <name>` | Switch the active model |
| `/stats` | Response time statistics |
| `/context-usage` | Context window usage |
| `/cron add\|list\|remove` | Manage scheduled tasks |
| `/autojob <task>` | Generate and execute an autonomous job |
| `/help` | List all available commands |

## Cron / Scheduled Tasks

Run tasks on a schedule. Jobs are stored in `~/.qubito/cron.json`.

```bash
# Via slash command in chat:
/cron add 0 8 * * * morning-digest :: summarize my unread messages
/cron list
/cron remove <id>

# Via API:
curl -X POST http://127.0.0.1:8741/cron \
  -H "Content-Type: application/json" \
  -d '{"name": "morning", "cron_expression": "0 8 * * *", "action": "summarize inbox"}'
```

If `channel_target` is set (e.g. `"telegram:123456"`), the result is pushed to that channel.

## Webhooks

Receive external events and trigger agent actions. Configs stored in `~/.qubito/webhooks.json`.

```bash
# Create a webhook via API
curl -X POST http://127.0.0.1:8741/webhooks \
  -d '{"name": "github-pr", "action_template": "PR {pull_request.title} was merged", "channel_target": "telegram:123"}'

# Point GitHub to: http://your-host:8741/webhooks/<webhook-id>
```

Supports HMAC signature verification via `X-Hub-Signature-256` when a `secret` is configured.

## Multi-Agent Routing

### Named agents

Register agents with specific characters, tools, and RAG namespaces:

```bash
curl -X POST http://127.0.0.1:8741/agents \
  -H "Content-Type: application/json" \
  -d '{"id": "work", "character": "joey", "rag_namespace": "work-docs", "description": "Work assistant"}'
```

Create a session for a specific agent:

```bash
curl -X POST http://127.0.0.1:8741/sessions \
  -d '{"agent_id": "work"}'
```

### Routing rules

Auto-select agents based on channel context:

```bash
# Route all Telegram messages to the "work" agent
curl -X POST http://127.0.0.1:8741/routes \
  -d '{"pattern": "telegram:*", "agent_id": "work", "priority": 10}'

# Route a specific Discord channel to "support"
curl -X POST http://127.0.0.1:8741/routes \
  -d '{"pattern": "discord:123456", "agent_id": "support", "priority": 20}'
```

Patterns use glob syntax. Higher priority rules match first.

### Workspace isolation

Each agent can have its own RAG namespace. Documents indexed by one agent don't leak to others. FAISS indexes are persisted to `~/.qubito/memory/{namespace}/`.

## Background Tasks

Submit long-running tasks that execute asynchronously:

```bash
curl -X POST http://127.0.0.1:8741/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Research the latest AI safety papers and summarize them"}'

# Check status
curl http://127.0.0.1:8741/tasks/<task-id>
```

## Configuration Structure

Two-tier config: project-local overrides global by filename.

```
~/.qubito/                  # Global (user defaults)
├── agents/                 # Character .md files
├── skills/                 # Slash command .md files
├── rules/                  # System prompt rules .md files
├── mcp/                    # MCP server configs (servers.json)
├── memory/                 # RAG indexes per namespace
├── jobs/                   # Autojob execution logs
├── qubito.db               # SQLite: sessions + messages
├── cron.json               # Scheduled tasks
├── webhooks.json           # Webhook configurations
├── agents.json             # Named agent registry
├── routing.json            # Channel routing rules
├── tokens.json             # API auth tokens (hashed)
├── approved_senders.json   # DM pairing approvals
├── audit.db                # Tamper-evident audit log
└── daemon.pid              # PID file

.qubito/                    # Project-local (overrides global)
├── agents/
├── skills/
├── rules/
└── mcp/
```

## Characters

Agents respond through configurable personalities defined as markdown files with YAML frontmatter:

```markdown
---
name: My Character
emoji: "🤖"
color: bold green
hi_message: "Hey there!"
bye_message: "See you later!"
thinking: "Hmm|Let me think|Processing..."
---

You are a helpful assistant who speaks in a friendly tone.
```

Drop a `.md` file into `agents/` or `~/.qubito/agents/` and it's instantly available.

## Architecture

```
 Channels                DaemonClient          Daemon (FastAPI)
┌────────────────┐            │           ┌───────────────────────────────┐
│ Channel (ABC)  │            │           │  SessionManager + SQLite      │
│  ├ CLIChannel  │───HTTP────►│───HTTP───►│    └ Agent                    │
│  ├ Telegram    │            │           │       ├ AIModelFacade         │
│  ├ Discord     │            │           │       ├ RAG (FAISS, namespaced)│
│  └ WebChat     │            │           │       └ MCP Tools             │
└────────────────┘            │           │                               │
                              │           │  EventBus (pub/sub)           │
  Push notifications ◄────────┤           │  Scheduler (cron)             │
  (Telegram/Discord API)      │           │  TaskQueue (background)       │
                              │           │  WebhookRouter                │
                              │           │  AgentRegistry + Router       │
                              │           │  TokenManager (auth)          │
                              │           │  AuditLog (hash chain)        │
                              │           │                               │
                              │           │  AI Providers                 │
                              │           │  ┌──────┬────────┐            │
                              │           │  │Ollama│ Gemini │            │
                              │           │  │OpenR.│ vLLM   │            │
                              │           │  └──────┴────────┘            │
                              │           └───────────────────────────────┘
```

### Key modules

| Module | Description |
|--------|-------------|
| `src/channels/` | Channel ABC + CLI, Telegram, Discord, push messaging |
| `src/cli/` | argparse entry point with all subcommands |
| `src/daemon/` | FastAPI server, session manager, client, lifecycle |
| `src/config/` | Two-tier path resolver |
| `src/agents/` | Agent class, character loader, registry, delegation |
| `src/genai/` | AI provider abstraction (Ollama, Gemini, OpenRouter) |
| `src/rag/` | FAISS document store with namespaced persistence |
| `src/mcp/` | MCP tool integration with crash recovery |
| `src/skills/` | Slash commands, autojob, cron handler |
| `src/scheduler/` | Cron job scheduler with croniter |
| `src/webhooks/` | Webhook receiver with HMAC verification |
| `src/tasks/` | Background task queue |
| `src/routing/` | Channel-to-agent routing rules |
| `src/security/` | Auth tokens, DM pairing, audit log |
| `src/persistence/` | SQLite conversation persistence |
| `src/bus/` | Async event bus (pub/sub) |
| `src/web/` | HTMX web dashboard |
| `src/webchat/` | Standalone chat web UI |

## Development

```bash
uv sync --extra dev
uv run pytest -v        # Run all tests (51 tests)
```
