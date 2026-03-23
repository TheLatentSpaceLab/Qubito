"""Telegram bot interface for the Friends chatbot."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.agents.agent import Agent
from src.agents.agent_manager import AgentManager
from src.constants import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

# Map chat_id → Agent so each conversation keeps its own state
_agents: dict[int, Agent] = {}


def _telegram_on_tool_call(_self: Agent, tool_name: str, arguments: dict) -> bool:
    """Log tool usage (no interactive confirmation in Telegram)."""
    args_summary = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    logger.info("🔧 %s(%s)", tool_name, args_summary)
    return True


def _get_agent(chat_id: int) -> Agent:
    """Return the cached agent for a chat, creating one if needed."""
    if chat_id not in _agents:
        agent = AgentManager.start_agent()
        agent.on_tool_call = _telegram_on_tool_call.__get__(agent, Agent)
        _agents[chat_id] = agent
    return _agents[chat_id]


async def _run_sync(func: partial) -> str:  # type: ignore[type-arg]
    """Run a blocking Agent call in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, func)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet with the character's intro."""
    agent = _get_agent(update.effective_chat.id)
    greeting = agent.get_start_message()
    await update.message.reply_text(f"{agent.emoji} {greeting}")


async def cmd_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /change — switch to a new random character."""
    chat_id = update.effective_chat.id
    _agents.pop(chat_id, None)
    AgentManager.AGENTS.clear()
    agent = _get_agent(chat_id)
    greeting = agent.get_start_message()
    await update.message.reply_text(
        f"Nuevo personaje: {agent.emoji} *{agent.name}*\n\n{greeting}",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    agent = _get_agent(update.effective_chat.id)

    await update.message.chat.send_action("typing")

    try:
        response = await _run_sync(partial(agent.message, update.message.text))
    except Exception:
        logger.exception("Error generating response")
        response = "Sorry, I'm not feeling very well. 🤒"

    # Telegram has a 4096 char limit per message
    for i in range(0, len(response), 4096):
        await update.message.reply_text(response[i:i + 4096])


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files — transcribe then respond."""
    from src.stt.transcriber import transcribe

    agent = _get_agent(update.effective_chat.id)
    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as tmp:
        ogg_path = Path(tmp) / "voice.ogg"
        await file.download_to_drive(str(ogg_path))

        await update.message.chat.send_action("typing")
        text = await _run_sync(partial(transcribe, ogg_path))

    if not text.strip():
        await update.message.reply_text("No pude entender el audio. ¿Podés repetir?")
        return

    logger.info("Voice transcription: %s", text)
    await update.message.reply_text(f"🎙️ _{text}_", parse_mode="Markdown")

    await update.message.chat.send_action("typing")
    try:
        response = await _run_sync(partial(agent.message, text))
    except Exception:
        logger.exception("Error generating response")
        response = "Sorry, I'm not feeling very well. 🤒"

    for i in range(0, len(response), 4096):
        await update.message.reply_text(response[i:i + 4096])


def run_bot() -> None:
    """Start the Telegram bot (blocking)."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set. Add it to your .env file."
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("change", cmd_change))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    async def _set_commands(application: Application) -> None:
        await application.bot.set_my_commands([
            BotCommand("start", "Saludar al personaje"),
            BotCommand("change", "Cambiar de personaje"),
        ])

    app.post_init = _set_commands

    logger.info("Telegram bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
