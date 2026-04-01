from __future__ import annotations

from pathlib import Path

import pytest

from src.skills.skill_loader import SkillData, _parse_skill_file, load_all_skills
from src.skills.registry import SkillRegistry


class TestParseSkillFile:
    def test_valid_skill(self, sample_skill_md: Path) -> None:
        skill = _parse_skill_file(sample_skill_md)
        assert skill.name == "ping"
        assert skill.description == "Replies with pong"
        assert "Ping skill" in skill.instructions

    def test_valid_llm_skill(self, sample_llm_skill_md: Path) -> None:
        skill = _parse_skill_file(sample_llm_skill_md)
        assert skill.name == "summarize"
        assert skill.description == "Summarizes text"

    def test_missing_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "bad"
        skill_dir.mkdir()
        p = skill_dir / "SKILL.md"
        p.write_text("no frontmatter")
        with pytest.raises(ValueError, match="missing frontmatter"):
            _parse_skill_file(p)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "incomplete"
        skill_dir.mkdir()
        p = skill_dir / "SKILL.md"
        p.write_text('---\nname: "test"\n---\nBody.\n')
        with pytest.raises(ValueError, match="missing required field"):
            _parse_skill_file(p)


class TestLoadAllSkills:
    def test_loads_and_deduplicates(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"

        for d in (dir_a / "test", dir_b / "test"):
            d.mkdir(parents=True)

        content = (
            '---\n'
            'name: "test"\n'
            'description: "A test"\n'
            '---\n\nInstructions.\n'
        )
        (dir_a / "test" / "SKILL.md").write_text(content)
        (dir_b / "test" / "SKILL.md").write_text(content.replace("A test", "Different"))

        skills = load_all_skills(dirs=[dir_a, dir_b])
        assert len(skills) == 1
        assert skills[0].description == "A test"  # first dir wins


class TestSkillRegistry:
    def _make_registry(self) -> SkillRegistry:
        skills = [
            SkillData("ping", "Ping", ""),
            SkillData("summarize", "Summarize", "Summarize text."),
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
