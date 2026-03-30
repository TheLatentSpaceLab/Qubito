from __future__ import annotations

from pathlib import Path

import pytest

import src.config.resolver as resolver_mod
from src.config.resolver import QConfig


@pytest.fixture(autouse=True)
def _isolate_legacy_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent the real project's legacy dirs from leaking into tests."""
    monkeypatch.setattr(resolver_mod, "_LEGACY_ROOT", tmp_path / "no_legacy")


class TestCollectDirs:
    def test_global_only(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "global"
        (global_dir / "agents").mkdir(parents=True)

        cfg = QConfig()
        cfg._global_dir = global_dir
        dirs = cfg.agents_dirs
        assert dirs == [global_dir / "agents"]

    def test_project_overrides_global(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "global"
        project_dir = tmp_path / "project"
        for base in (global_dir, project_dir / ".qubito"):
            (base / "skills").mkdir(parents=True)

        cfg = QConfig(project_dir=project_dir)
        cfg._global_dir = global_dir
        dirs = cfg.skills_dirs
        assert dirs[0] == project_dir / ".qubito" / "skills"
        assert dirs[1] == global_dir / "skills"

    def test_nonexistent_dirs_excluded(self, tmp_path: Path) -> None:
        cfg = QConfig()
        cfg._global_dir = tmp_path / "nonexistent"
        assert cfg.agents_dirs == []

    def test_all_resource_types(self, tmp_qubito_dir: Path) -> None:
        cfg = QConfig()
        cfg._global_dir = tmp_qubito_dir
        for prop in ("agents_dirs", "skills_dirs", "rules_dirs", "mcp_dirs"):
            dirs = getattr(cfg, prop)
            assert len(dirs) >= 1
            assert dirs[0].exists()


class TestMcpConfigPaths:
    def test_returns_existing_json(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "global"
        mcp = global_dir / "mcp"
        mcp.mkdir(parents=True)
        (mcp / "servers.json").write_text("{}")

        cfg = QConfig()
        cfg._global_dir = global_dir
        paths = cfg.mcp_config_paths()
        assert len(paths) == 1
        assert paths[0].name == "servers.json"

    def test_no_files_returns_empty(self, tmp_path: Path) -> None:
        cfg = QConfig()
        cfg._global_dir = tmp_path / "empty"
        assert cfg.mcp_config_paths() == []

    def test_project_before_global(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "global"
        project_dir = tmp_path / "project"
        for base in (global_dir / "mcp", project_dir / ".qubito" / "mcp"):
            base.mkdir(parents=True)
            (base / "servers.json").write_text("{}")

        cfg = QConfig(project_dir=project_dir)
        cfg._global_dir = global_dir
        paths = cfg.mcp_config_paths()
        assert len(paths) == 2
        assert "project" in str(paths[0])


class TestMemoryDir:
    def test_returns_global_memory(self, tmp_path: Path) -> None:
        cfg = QConfig()
        cfg._global_dir = tmp_path
        assert cfg.memory_dir == tmp_path / "memory"
