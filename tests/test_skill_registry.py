from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.skills.skill_loader import SkillData, _parse_skill_file, load_all_skills
from src.skills.registry import SkillRegistry


class TestParseSkillFile:
    def test_valid_handler_skill(self, sample_skill_md: Path) -> None:
        skill = _parse_skill_file(sample_skill_md)
        assert skill.name == "ping"
        assert skill.skill_type == "handler"
        assert skill.handler == "tests.helpers.handle_ping"
        assert "Ping skill" in skill.instructions

    def test_valid_llm_skill(self, sample_llm_skill_md: Path) -> None:
        skill = _parse_skill_file(sample_llm_skill_md)
        assert skill.name == "summarize"
        assert skill.skill_type == "llm"
        assert skill.handler is None

    def test_missing_frontmatter(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.md"
        p.write_text("no frontmatter")
        with pytest.raises(ValueError, match="missing frontmatter"):
            _parse_skill_file(p)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        p = tmp_path / "incomplete.md"
        p.write_text('---\nname: "test"\n---\nBody.\n')
        with pytest.raises(ValueError, match="missing required field"):
            _parse_skill_file(p)


class TestLoadAllSkills:
    def test_loads_and_deduplicates(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        content = (
            '---\n'
            'name: "test"\n'
            'description: "A test"\n'
            'type: "llm"\n'
            '---\n\nInstructions.\n'
        )
        (dir_a / "test.md").write_text(content)
        (dir_b / "test.md").write_text(content.replace("A test", "Different"))

        skills = load_all_skills(dirs=[dir_a, dir_b])
        assert len(skills) == 1
        assert skills[0].description == "A test"  # first dir wins


class TestSkillRegistry:
    def _make_registry(self) -> SkillRegistry:
        skills = [
            SkillData("ping", "Ping", "handler", "tests.helpers.handle_ping", ""),
            SkillData("summarize", "Summarize", "llm", None, "Summarize text."),
        ]
        return SkillRegistry(skills)

    def test_get_existing(self) -> None:
        reg = self._make_registry()
        skill = reg.get("ping")
        assert skill is not None
        assert skill.name == "ping"

    def test_get_nonexistent(self) -> None:
        reg = self._make_registry()
        assert reg.get("nonexistent") is None

    def test_list_all(self) -> None:
        reg = self._make_registry()
        assert len(reg.list_all()) == 2

    def test_execute_handler(self) -> None:
        reg = self._make_registry()
        skill = reg.get("ping")
        agent = MagicMock()
        reg.execute_handler(skill, agent, "/ping test")
        import tests.helpers
        assert tests.helpers._last_ping_input == "/ping test"

    def test_execute_handler_no_handler_raises(self) -> None:
        reg = self._make_registry()
        skill = reg.get("summarize")
        agent = MagicMock()
        with pytest.raises(ValueError, match="no handler"):
            reg.execute_handler(skill, agent, "/summarize text")
