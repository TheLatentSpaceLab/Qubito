from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.character_loader import (
    CharacterData,
    _collect_files,
    _parse_character_file,
    load_all_characters,
    load_character_by_filename,
)


class TestParseCharacterFile:
    def test_valid_file(self, sample_agent_md: Path) -> None:
        char = _parse_character_file(sample_agent_md)
        assert char.name == "Tester"
        assert char.emoji == "🧪"
        assert char.color == "bold cyan"
        assert char.hi_message == "Hello from tests!"
        assert char.bye_message == "Bye from tests!"
        assert char.thinking == ("Hmm", "Processing")
        assert "testing personality" in char.personality

    def test_missing_frontmatter(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.md"
        p.write_text("no frontmatter here")
        with pytest.raises(ValueError, match="missing frontmatter"):
            _parse_character_file(p)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        p = tmp_path / "incomplete.md"
        p.write_text(
            '---\nname: "Bot"\nemoji: "🤖"\n---\nBody.\n'
        )
        with pytest.raises(ValueError, match="missing required field"):
            _parse_character_file(p)

    def test_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "minimal.md"
        p.write_text(
            '---\n'
            'name: "Min"\n'
            'emoji: "⚡"\n'
            'color: "white"\n'
            'hi_message: "Hi"\n'
            '---\n\nPersonality.\n'
        )
        char = _parse_character_file(p)
        assert char.bye_message == "has left the chat."
        assert char.thinking == ()


class TestCollectFiles:
    def test_deduplicates_by_filename(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "bot.md").write_text("---\nname: A\n---\n")
        (dir_b / "bot.md").write_text("---\nname: B\n---\n")

        files = _collect_files([dir_a, dir_b])
        assert len(files) == 1
        assert files[0].parent == dir_a  # first dir wins

    def test_empty_dirs(self, tmp_path: Path) -> None:
        assert _collect_files([tmp_path]) == []


class TestLoadAllCharacters:
    def test_loads_from_dir(self, tmp_qubito_dir: Path, sample_agent_md: Path) -> None:
        agents_dir = tmp_qubito_dir / "agents"
        chars = load_all_characters(dirs=[agents_dir])
        assert len(chars) == 1
        assert chars[0].name == "Tester"


class TestLoadCharacterByFilename:
    def test_found(self, tmp_qubito_dir: Path, sample_agent_md: Path) -> None:
        agents_dir = tmp_qubito_dir / "agents"
        char = load_character_by_filename("tester", dirs=[agents_dir])
        assert char.name == "Tester"

    def test_not_found(self, tmp_qubito_dir: Path, sample_agent_md: Path) -> None:
        agents_dir = tmp_qubito_dir / "agents"
        with pytest.raises(FileNotFoundError, match="not found"):
            load_character_by_filename("nonexistent", dirs=[agents_dir])
