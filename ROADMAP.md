# Qubito Roadmap — Toward an OpenClaw-like Architecture

> Goal: Transform Qubito from an interactive CLI chat into a **persistent background agent**
> that connects to multiple messaging channels and acts autonomously on your behalf.

---

## Phase 0 — Stabilize the Foundation

_Priority: things that are stubbed or broken today._

- [ ] **Conversation persistence** — save/load chat history to disk (SQLite or JSON lines) so context survives restarts. `Agent._load_recent_conversations()` currently returns `[]`.
- [ ] **PDF extraction** — implement the `/load` handler for PDFs (currently `NotImplementedError`).
- [ ] **Test suite** — add at least unit tests for config resolution, character loading, skill registry, and the tool-call loop. There are zero tests today.
- [ ] **Error resilience** — graceful handling of provider timeouts, MCP server crashes, and malformed tool responses so the agent doesn't die.

---

## Phase 1 — Background Daemon (the Gateway)

_This is the single biggest architectural shift. OpenClaw's core is a long-running gateway process._

- [ ] **Daemon mode** (`qubito daemon start/stop/status`)
  - Run as a `systemd --user` service on Linux (like OpenClaw uses launchd/systemd).
  - PID file + health-check endpoint.
  - Auto-restart on crash.
- [ ] **Event bus / message router**
  - Internal pub/sub (asyncio queues or a lightweight broker) that decouples _channels_ from _agents_.
  - Inbound message → route to correct agent → response back to originating channel.
- [ ] **Session manager**
  - Track per-channel, per-user sessions with conversation history.
  - Session timeout / eviction policy.
- [ ] **Local API**
  - WebSocket or HTTP server on `127.0.0.1` (like OpenClaw's `ws://127.0.0.1:18789`).
  - Endpoints: `POST /message`, `GET /sessions`, `GET /status`, `POST /agent/switch`.
  - This becomes the single control plane everything else talks to.

---

## Phase 2 — Multi-Channel Support

_OpenClaw's killer feature is 25+ channel integrations. Start with high-value ones._

- [ ] **Channel abstraction** — define a `Channel` interface: `receive()`, `send()`, `channel_id`, `user_id`.
- [ ] **Refactor Telegram** to implement the `Channel` interface and connect through the event bus instead of running standalone.
- [ ] **WhatsApp** — via Baileys (JS) or whatsapp-web.js running as an MCP server / subprocess.
- [ ] **Discord** — discord.py bot connecting through the channel abstraction.
- [ ] **Slack** — Slack Bolt app as a channel.
- [ ] **Signal** — via signal-cli or signald.
- [ ] **WebChat** — simple web UI served by the local API (HTML + WebSocket).
- [ ] **CLI** — refactor `cmd_chat.py` to be a thin client that talks to the daemon API instead of running the agent in-process.

---

## Phase 3 — Autonomous Agent Loop

_Move from "respond when asked" to "act on schedule and react to events."_

- [ ] **Cron / scheduled tasks**
  - `qubito cron add "every morning at 8am" "summarize my unread messages"`
  - Stored in config, executed by the daemon.
- [ ] **Webhooks**
  - HTTP endpoint on the local API that triggers agent actions.
  - GitHub webhook → "PR #42 was merged" → agent posts to Slack.
- [ ] **Proactive actions**
  - Agent can initiate messages (reminders, digests, alerts) without user prompt.
  - Configurable per-channel: opt-in to proactive messages.
- [ ] **Background tasks**
  - Long-running tasks (web research, file processing) that the agent works on asynchronously.
  - Status reporting: "I'm 60% done with your research task."

---

## Phase 4 — Multi-Agent Routing

_OpenClaw can route different channels/accounts to isolated agents._

- [ ] **Agent registry** — manage multiple named agents, each with its own character, tools, and RAG store.
- [ ] **Routing rules** — map channels/users to specific agents:
  - "Route my Telegram DMs to the work agent."
  - "Route the Discord #support channel to the support agent."
- [ ] **Agent-to-agent communication** — agents can delegate to or consult other agents.
- [ ] **Workspace isolation** — each agent gets its own conversation history, RAG index, and MCP server set.

---

## Phase 5 — Web Control UI

_OpenClaw ships a web-based control panel served by the gateway._

- [ ] **Dashboard** — agent status, active sessions, recent messages, system health.
- [ ] **Configuration UI** — manage agents, channels, skills, rules, cron jobs without editing files.
- [ ] **Chat UI** — WebChat interface for direct interaction (alternative to CLI).
- [ ] **Logs & observability** — searchable message history, tool call traces, error logs.
- [ ] **Tech**: lightweight framework (FastAPI + HTMX, or a small React/Svelte app).

---

## Phase 6 — Skills Platform

_Extend the current slash-command system into a proper skills marketplace._

- [ ] **Skill packaging** — skills as self-contained directories with dependencies, not just markdown files.
- [ ] **Skill tiers**: bundled (ships with Qubito), managed (installed from registry), workspace (project-local).
- [ ] **Skill discovery** — `qubito skill search "calendar"`, `qubito skill install <name>`.
- [ ] **Skill SDK** — documented API for third-party skill authors.
- [ ] **Permission model** — skills declare what they need (network, filesystem, channels) and users approve.

---

## Phase 7 — Companion Apps & Voice

_OpenClaw has macOS/iOS/Android companion apps with voice wake words._

- [ ] **Voice mode** — always-on microphone with wake word detection (extend existing STT).
- [ ] **TTS responses** — text-to-speech output for voice conversations.
- [ ] **Desktop tray app** — system tray icon with quick-chat popup (Electron or Tauri).
- [ ] **Mobile node** — lightweight app that connects to your daemon, forwards voice/camera.

---

## Phase 8 — Security & Privacy

- [ ] **DM pairing** — unknown senders must be approved before the agent responds (OpenClaw does this).
- [ ] **End-to-end encryption** for channel ↔ daemon communication.
- [ ] **Audit log** — immutable record of all agent actions for review.
- [ ] **Tool sandboxing** — MCP servers run in containers or with restricted permissions.
- [ ] **Auth for local API** — token-based auth so only authorized clients connect to the daemon.

---

## Suggested Execution Order

```
Now          Phase 0  — Stabilize (persistence, PDF, tests, error handling)
             Phase 1  — Daemon + local API (the architectural pivot)
             Phase 2  — Multi-channel (Telegram refactor, WhatsApp, Discord)
             Phase 3  — Cron, webhooks, proactive actions
Later        Phase 4  — Multi-agent routing
             Phase 5  — Web control UI
             Phase 6  — Skills platform
Eventually   Phase 7  — Companion apps & voice
             Phase 8  — Security hardening
```

Phases 0-2 are the critical path. Once Qubito runs as a daemon with a channel abstraction and local API, everything else layers on top naturally.

---

## Key Architectural Decisions to Make Early

| Decision | Options | OpenClaw's choice |
|----------|---------|-------------------|
| Daemon process manager | systemd user service vs supervisor vs custom | systemd/launchd |
| Internal messaging | asyncio queues vs Redis vs ZeroMQ | WebSocket-based |
| Local API protocol | HTTP REST vs WebSocket vs gRPC | WebSocket |
| Persistence | SQLite vs PostgreSQL vs JSON files | SQLite recommended for local-first |
| Web UI framework | FastAPI+HTMX vs Next.js vs Svelte | Node/React (OpenClaw is TS) |
| Channel subprocess model | In-process vs child process vs MCP server | In-process (OpenClaw) |
