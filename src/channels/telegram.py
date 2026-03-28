"""Telegram channel implementation."""

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

from src.channels.base import Channel
from src.daemon.client import DaemonClient

logger = logging.getLogger(__name__)


class TelegramChannel(Channel):
    """Telegram bot channel that bridges Telegram chats to the daemon."""

    def __init__(self, token: str, client: DaemonClient | None = None) -> None:
        super().__init__(client)
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set. Add it to your .env file.")
        self._token = token
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._sessions: dict[int, str] = {}
        self._meta: dict[int, dict] = {}
        self._app: Application | None = None

    def start(self) -> None:
        """Build the Telegram Application and run polling (blocking)."""
        self.ensure_daemon()
        self._setup_logging()

        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("change", self._cmd_change))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
        )
        self._app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice),
        )
        self._app.post_init = self._set_commands

        logger.info("Telegram bot starting (daemon mode)...")
        self._app.run_polling(allowed_updates=Update.ALL_TYPES)

    def stop(self) -> None:
        """Signal the bot to stop."""
        if self._app:
            self._app.stop_running()
        self._executor.shutdown(wait=False)

    def _ensure_session(self, chat_id: int) -> str:
        """Return session_id for this chat, creating one if needed."""
        if chat_id not in self._sessions:
            session = self.client.create_session()
            self._sessions[chat_id] = session.id
            self._meta[chat_id] = {
                "name": session.character_name,
                "emoji": session.emoji,
                "color": session.color,
                "hi_message": session.hi_message,
            }
        return self._sessions[chat_id]

    async def _send_to_daemon(self, session_id: str, text: str) -> str:
        """Send a message to the daemon in a thread pool."""
        loop = asyncio.get_running_loop()
        response, _ = await loop.run_in_executor(
            self._executor,
            partial(self.client.send_message, session_id, text),
        )
        return response

    async def _cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /start -- greet with the character's intro."""
        chat_id = update.effective_chat.id
        self._ensure_session(chat_id)
        meta = self._meta[chat_id]
        await update.message.reply_text(f"{meta['emoji']} {meta['hi_message']}")

    async def _cmd_change(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /change -- switch to a new random character."""
        chat_id = update.effective_chat.id

        old_sid = self._sessions.pop(chat_id, None)
        if old_sid:
            self.client.delete_session(old_sid)
        self._meta.pop(chat_id, None)

        self._ensure_session(chat_id)
        meta = self._meta[chat_id]
        await update.message.reply_text(
            f"Nuevo personaje: {meta['emoji']} *{meta['name']}*\n\n{meta['hi_message']}",
            parse_mode="Markdown",
        )

    async def _handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle regular text messages."""
        chat_id = update.effective_chat.id
        session_id = self._ensure_session(chat_id)

        await update.message.chat.send_action("typing")

        try:
            response = await self._send_to_daemon(session_id, update.message.text)
        except Exception:
            logger.exception("Error generating response")
            response = "Sorry, I'm not feeling very well."

        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i : i + 4096])

    async def _handle_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle voice/audio messages -- transcribe then respond."""
        from src.stt.transcriber import transcribe

        chat_id = update.effective_chat.id
        session_id = self._ensure_session(chat_id)
        voice = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice.file_id)

        with tempfile.TemporaryDirectory() as tmp:
            ogg_path = Path(tmp) / "voice.ogg"
            await file.download_to_drive(str(ogg_path))

            await update.message.chat.send_action("typing")
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(
                self._executor, partial(transcribe, ogg_path),
            )

        if not text.strip():
            await update.message.reply_text("No pude entender el audio.")
            return

        logger.info("Voice transcription: %s", text)
        await update.message.reply_text(f"\U0001f399\ufe0f _{text}_", parse_mode="Markdown")

        await update.message.chat.send_action("typing")
        try:
            response = await self._send_to_daemon(session_id, text)
        except Exception:
            logger.exception("Error generating response")
            response = "Sorry, I'm not feeling very well."

        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i : i + 4096])

    @staticmethod
    async def _set_commands(application: Application) -> None:
        """Register bot commands in the Telegram menu."""
        await application.bot.set_my_commands([
            BotCommand("start", "Saludar al personaje"),
            BotCommand("change", "Cambiar de personaje"),
        ])

    @staticmethod
    def _setup_logging() -> None:
        """Configure logging for the Telegram bot process."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
