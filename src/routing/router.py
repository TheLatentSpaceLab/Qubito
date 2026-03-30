"""Message router that resolves channel context to agent IDs via glob patterns."""

from __future__ import annotations

import fnmatch
from logging import getLogger

from src.routing.models import RoutingRule, load_routing_rules

logger = getLogger(__name__)


class MessageRouter:
    """Routes inbound messages to the correct agent based on channel context."""

    def __init__(self) -> None:
        self._rules: list[RoutingRule] = []
        self.load()

    def load(self) -> None:
        """Reload rules from disk, sorted by priority descending."""
        self._rules = sorted(load_routing_rules(), key=lambda r: -r.priority)
        logger.info("Loaded %d routing rule(s)", len(self._rules))

    @property
    def rules(self) -> list[RoutingRule]:
        return list(self._rules)

    def resolve(
        self,
        channel_type: str,
        channel_id: str,
        user_id: str | None = None,
    ) -> str | None:
        """Find the agent_id for the given channel context.

        Patterns are glob-style strings matched against ``"channel_type:channel_id"``.
        Examples: ``"telegram:*"``, ``"discord:123:456"``, ``"slack:TEAM:*"``.

        Parameters
        ----------
        channel_type : str
            Platform name (``telegram``, ``discord``, etc.).
        channel_id : str
            Channel-specific identifier.
        user_id : str or None
            Optional user identifier for user-level routing.

        Returns
        -------
        str or None
            The matched agent_id, or None if no rule matches.
        """
        target = f"{channel_type}:{channel_id}"
        for rule in self._rules:
            if not rule.enabled:
                continue
            if fnmatch.fnmatch(target, rule.pattern):
                logger.debug("Route matched: %s -> agent '%s'", target, rule.agent_id)
                return rule.agent_id
        return None
