from __future__ import annotations

from src.skills.skill_loader import SkillData


class SkillRegistry:
    """Maps slash commands to skill definitions."""

    def __init__(self, skills: list[SkillData]) -> None:
        self._skills: dict[str, SkillData] = {s.name: s for s in skills}

    def get(self, name: str) -> SkillData | None:
        return self._skills.get(name)

    def list_all(self) -> list[SkillData]:
        return list(self._skills.values())
