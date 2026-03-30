"""Token-based authentication for the daemon API."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, asdict
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".qubito" / "tokens.json"


@dataclass
class TokenInfo:
    """Metadata for a registered API token."""

    name: str
    token_hash: str
    scopes: list[str]


class TokenManager:
    """Manages API tokens with SHA-256 hashing and JSON persistence."""

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._tokens: list[TokenInfo] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._tokens = [TokenInfo(**t) for t in data]
        except Exception:
            logger.warning("Failed to load tokens from %s", self._path, exc_info=True)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([asdict(t) for t in self._tokens], indent=2))

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_token(self, name: str, scopes: list[str] | None = None) -> str:
        """Create a new token. Returns the plaintext (shown once).

        Parameters
        ----------
        name : str
            Human-readable name for the token.
        scopes : list of str or None
            Permission scopes. Defaults to ["read", "write", "chat"].

        Returns
        -------
        str
            The plaintext token (only shown at creation time).
        """
        scopes = scopes or ["read", "write", "chat"]
        plaintext = f"qbt_{secrets.token_urlsafe(32)}"
        info = TokenInfo(name=name, token_hash=self._hash(plaintext), scopes=scopes)
        self._tokens.append(info)
        self._save()
        return plaintext

    def verify_token(self, token: str) -> TokenInfo | None:
        """Verify a plaintext token and return its info, or None if invalid."""
        h = self._hash(token)
        for info in self._tokens:
            if info.token_hash == h:
                return info
        return None

    def list_tokens(self) -> list[dict]:
        """Return token metadata (without hashes) for display."""
        return [{"name": t.name, "scopes": t.scopes} for t in self._tokens]

    def revoke_token(self, name: str) -> bool:
        """Revoke a token by name. Returns True if found."""
        before = len(self._tokens)
        self._tokens = [t for t in self._tokens if t.name != name]
        if len(self._tokens) < before:
            self._save()
            return True
        return False
