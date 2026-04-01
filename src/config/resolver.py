"""Qubito configuration resolver.

Primary config lives at ~/.qubito/ (global, machine-wide).
Optional project overrides via .qubito/ in a project directory.
Legacy fallback: project root directories (agents/, skills/, etc.)
"""

from __future__ import annotations

from pathlib import Path

_GLOBAL_DIR = Path.home() / ".qubito"
_LEGACY_ROOT = Path(__file__).resolve().parent.parent.parent


class QConfig:
    """Resolved configuration paths for a Qubito session."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._global_dir = _GLOBAL_DIR
        self._project_dir = project_dir
        self._project_qubito = (project_dir / ".qubito") if project_dir else None

    @property
    def global_dir(self) -> Path:
        return self._global_dir

    @property
    def project_dir(self) -> Path | None:
        return self._project_dir

    @property
    def agents_dirs(self) -> list[Path]:
        return self._collect_dirs("agents")

    @property
    def skills_dirs(self) -> list[Path]:
        return self._collect_dirs("skills")

    @property
    def rules_dirs(self) -> list[Path]:
        return self._collect_dirs("rules")

    @property
    def mcp_dirs(self) -> list[Path]:
        return self._collect_dirs("mcp")

    @property
    def memory_dir(self) -> Path:
        return self._global_dir / "memory"

    @property
    def db_path(self) -> Path:
        return self._global_dir / "qubito.db"

    def mcp_config_paths(self) -> list[Path]:
        """Return all existing MCP config JSON files, highest priority first."""
        candidates: list[Path] = []
        # Project override
        if self._project_qubito:
            p = self._project_qubito / "mcp" / "servers.json"
            if p.exists():
                candidates.append(p)
        # Global
        p = self._global_dir / "mcp" / "servers.json"
        if p.exists():
            candidates.append(p)
        # Claude Code convention (.mcp.json at project root)
        p = _LEGACY_ROOT / ".mcp.json"
        if p.exists():
            candidates.append(p)
        # Legacy fallback
        p = _LEGACY_ROOT / "mcp_servers.json"
        if p.exists():
            candidates.append(p)
        return candidates

    def _collect_dirs(self, resource: str) -> list[Path]:
        """Return directories for a resource, highest priority first.

        Order: project .qubito/ > ~/.qubito/ > legacy project root.
        """
        dirs: list[Path] = []
        if self._project_qubito:
            d = self._project_qubito / resource
            if d.is_dir():
                dirs.append(d)
        d = self._global_dir / resource
        if d.is_dir():
            dirs.append(d)
        d = _LEGACY_ROOT / resource
        if d.is_dir():
            dirs.append(d)
        return dirs
