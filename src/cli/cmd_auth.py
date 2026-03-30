"""Handler for the ``qubito auth`` subcommand."""

from __future__ import annotations


def run_auth(action: str, name: str | None = None, scopes: str | None = None) -> None:
    """Manage API authentication tokens."""
    from src.security.auth import TokenManager

    mgr = TokenManager()

    if action == "create-token":
        if not name:
            print("Error: --name is required for create-token")
            return
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else None
        token = mgr.create_token(name, scope_list)
        print(f"Token created for '{name}':")
        print(f"  {token}")
        print("  (save this — it will not be shown again)")
    elif action == "list-tokens":
        tokens = mgr.list_tokens()
        if not tokens:
            print("No tokens configured.")
            return
        for t in tokens:
            print(f"  {t['name']}: scopes={','.join(t['scopes'])}")
    elif action == "revoke-token":
        if not name:
            print("Error: --name is required for revoke-token")
            return
        if mgr.revoke_token(name):
            print(f"Token '{name}' revoked.")
        else:
            print(f"Token '{name}' not found.")
    else:
        print(f"Unknown action: {action}. Use create-token, list-tokens, or revoke-token.")
