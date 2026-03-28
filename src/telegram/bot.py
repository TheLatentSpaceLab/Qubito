"""Telegram bot interface for the Qubito chatbot.

Connects to the daemon API when available, falls back to in-process agents.
"""

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

from src.constants import TELEGRAM_BOT_TOKEN
from src.daemon.client import DaemonClient

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

# Map chat_id → daemon session_id
_sessions: dict[int, str] = {}
# Cache character metadata per chat
_meta: dict[int, dict] = {}

_client: DaemonClient | None = None


def _get_client() -> DaemonClient:
    global _client
    if _client is None:
        _client = DaemonClient()
    return _client


def _ensure_session(chat_id: int) -> str:
    """Return session_id for this chat, creating one if needed."""
    if chat_id not in _sessions:
        client = _get_client()
        session = client.create_session()
        _sessions[chat_id] = session.id
        _meta[chat_id] = {
            "name": session.character_name,
            "emoji": session.emoji,
            "color": session.color,
            "hi_message": session.hi_message,
        }
    return _sessions[chat_id]


async def _send_to_daemon(session_id: str, text: str) -> str:
    """Send a message to the daemon in a thread pool."""
    client = _get_client()
    loop = asyncio.get_running_loop()
    response, _ = await loop.run_in_executor(
        _executor, partial(client.send_message, session_id, text)
    )
    return response


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet with the character's intro."""
    chat_id = update.effective_chat.id
    _ensure_session(chat_id)
    meta = _meta[chat_id]
    await update.message.reply_text(f"{meta['emoji']} {meta['hi_message']}")


async def cmd_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /change — switch to a new random character."""
    chat_id = update.effective_chat.id
    client = _get_client()

    old_sid = _sessions.pop(chat_id, None)
    if old_sid:
        client.delete_session(old_sid)
    _meta.pop(chat_id, None)

    _ensure_session(chat_id)
    meta = _meta[chat_id]
    await update.message.reply_text(
        f"Nuevo personaje: {meta['emoji']} *{meta['name']}*\n\n{meta['hi_message']}",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    chat_id = update.effective_chat.id
    session_id = _ensure_session(chat_id)

    await update.message.chat.send_action("typing")

    try:
        response = await _send_to_daemon(session_id, update.message.text)
    except Exception:
        logger.exception("Error generating response")
        response = "Sorry, I'm not feeling very well."

    for i in range(0, len(response), 4096):
        await update.message.reply_text(response[i : i + 4096])


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files — transcribe then respond."""
    from src.stt.transcriber import transcribe

    chat_id = update.effective_chat.id
    session_id = _ensure_session(chat_id)
    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as tmp:
        ogg_path = Path(tmp) / "voice.ogg"
        await file.download_to_drive(str(ogg_path))

        await update.message.chat.send_action("typing")
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(_executor, partial(transcribe, ogg_path))

    if not text.strip():
        await update.message.reply_text("No pude entender el audio.")
        return

    logger.info("Voice transcription: %s", text)
    await update.message.reply_text(f"🎙️ _{text}_", parse_mode="Markdown")

    await update.message.chat.send_action("typing")
    try:
        response = await _send_to_daemon(session_id, text)
    except Exception:
        logger.exception("Error generating response")
        response = "Sorry, I'm not feeling very well."

    for i in range(0, len(response), 4096):
        await update.message.reply_text(response[i : i + 4096])


def run_bot() -> None:
    """Start the Telegram bot (blocking). Requires the daemon to be running."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set. Add it to your .env file.")

    client = _get_client()
    if not client.is_daemon_running():
        raise RuntimeError(
            "Daemon is not running. Start it first with: qubito daemon start"
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

    logger.info("Telegram bot starting (daemon mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
