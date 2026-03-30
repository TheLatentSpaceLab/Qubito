from __future__ import annotations

from pathlib import Path

import pytest

from src.persistence.conversation_db import ConversationDB


@pytest.fixture()
def db(tmp_path: Path) -> ConversationDB:
    return ConversationDB(tmp_path / "test.db")


class TestSessionCRUD:
    def test_save_and_load(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        rows = db.load_sessions()
        assert len(rows) == 1
        assert rows[0]["id"] == "s1"
        assert rows[0]["character_name"] == "Bot"

    def test_delete_removes_session_and_messages(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        db.save_message("s1", {"role": "user", "content": "hi"})
        db.delete_session("s1")
        assert db.load_sessions() == []
        assert db.load_messages("s1") == []

    def test_touch_updates_last_active(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        before = db.load_sessions()[0]["last_active"]
        db.touch_session("s1")
        after = db.load_sessions()[0]["last_active"]
        assert after >= before

    def test_upsert_on_duplicate(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        db.save_session("s1", "Bot", "🤖", "cyan")
        assert len(db.load_sessions()) == 1


class TestMessageCRUD:
    def test_save_and_load_basic(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        db.save_message("s1", {"role": "user", "content": "hello"})
        db.save_message("s1", {"role": "assistant", "content": "hi there"})
        msgs = db.load_messages("s1")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_load_respects_limit(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        for i in range(10):
            db.save_message("s1", {"role": "user", "content": f"msg {i}"})
        msgs = db.load_messages("s1", limit=3)
        assert len(msgs) == 3
        # Should be the 3 most recent, in chronological order
        assert msgs[0]["content"] == "msg 7"
        assert msgs[2]["content"] == "msg 9"

    def test_tool_call_fields(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        tc_msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "read_file"}}],
        }
        db.save_message("s1", tc_msg)
        result_msg = {
            "role": "tool",
            "content": "file contents",
            "tool_call_id": "tc1",
            "name": "read_file",
        }
        db.save_message("s1", result_msg)

        msgs = db.load_messages("s1")
        assert len(msgs) == 2
        assert msgs[0]["tool_calls"][0]["id"] == "tc1"
        assert msgs[1]["tool_call_id"] == "tc1"
        assert msgs[1]["name"] == "read_file"

    def test_empty_session_returns_empty(self, db: ConversationDB) -> None:
        assert db.load_messages("nonexistent") == []

    def test_messages_isolated_by_session(self, db: ConversationDB) -> None:
        db.save_session("s1", "Bot", "🤖", "cyan")
        db.save_session("s2", "Bot2", "🧪", "red")
        db.save_message("s1", {"role": "user", "content": "for s1"})
        db.save_message("s2", {"role": "user", "content": "for s2"})
        assert len(db.load_messages("s1")) == 1
        assert db.load_messages("s1")[0]["content"] == "for s1"
