"""Action registry for trigger handlers.

Actions are async functions that execute when a trigger matches.
The registry provides a central place to register and fire handlers.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from agentwire.watcher import Trigger

logger = logging.getLogger(__name__)

# Action handler signature: (trigger, match, room) -> None
ActionHandler = Callable[["Trigger", re.Match[str], Any], Awaitable[None]]


@dataclass
class ActionRegistry:
    """Registry of action handlers.

    Handlers are async functions that execute when a trigger fires.
    Multiple handlers can be registered for different action types.

    Example:
        registry = ActionRegistry()

        @registry.handler("tts")
        async def tts_action(trigger, match, room):
            text = trigger.config.get("template", match.group(0))
            await room.speak(text)

        # Later, when trigger matches:
        await registry.fire("tts", trigger, match, room)
    """

    handlers: dict[str, ActionHandler] = field(default_factory=dict)

    def register(self, name: str, handler: ActionHandler) -> None:
        """Register an action handler.

        Args:
            name: Action name (e.g., "tts", "notify", "popup")
            handler: Async function(trigger, match, room) -> None
        """
        self.handlers[name] = handler

    def handler(self, name: str) -> Callable[[ActionHandler], ActionHandler]:
        """Decorator to register an action handler.

        Example:
            @registry.handler("tts")
            async def tts_action(trigger, match, room):
                ...
        """

        def decorator(fn: ActionHandler) -> ActionHandler:
            self.register(name, fn)
            return fn

        return decorator

    async def fire(
        self,
        action: str,
        trigger: "Trigger",
        match: re.Match[str],
        room: Any,
    ) -> None:
        """Fire an action by name.

        Args:
            action: The action name to fire
            trigger: The Trigger that matched
            match: The regex Match object
            room: The Room where the trigger fired
        """
        handler = self.handlers.get(action)
        if handler:
            try:
                await handler(trigger, match, room)
            except Exception:
                logger.exception("Action '%s' failed for trigger '%s'", action, trigger.name)
        else:
            logger.warning("Unknown action '%s' for trigger '%s'", action, trigger.name)

    def has(self, action: str) -> bool:
        """Check if an action handler is registered."""
        return action in self.handlers

    def list_actions(self) -> list[str]:
        """Return list of registered action names."""
        return list(self.handlers.keys())


# Global registry instance for built-in actions
default_registry = ActionRegistry()


# --- Built-in Action Handlers ---


@default_registry.handler("notify")
async def notify_action(trigger: "Trigger", match: re.Match[str], room: Any) -> None:
    """Send browser notification to connected clients.

    Config options:
        title: Notification title (default: "AgentWire")
        body: Body template with format placeholders for match groups

    Example trigger config:
        action: notify
        title: "Build Status"
        body: "Build {0} completed"
    """
    title = trigger.config.get("title", "AgentWire")
    body_template = trigger.config.get("body", "{0}")
    body = body_template.format(*match.groups(), **match.groupdict())

    await room.broadcast({
        "type": "notify",
        "title": title,
        "body": body,
    })


@default_registry.handler("send_keys")
async def send_keys_action(trigger: "Trigger", match: re.Match[str], room: Any) -> None:
    """Send keystrokes to the tmux session.

    Config options:
        keys: Key sequence template with format placeholders for match groups

    Example trigger config:
        action: send_keys
        keys: "y\n"  # Send 'y' followed by Enter
    """
    keys_template = trigger.config.get("keys", "")
    keys = keys_template.format(*match.groups(), **match.groupdict())

    await room.send_input(keys)


@default_registry.handler("broadcast")
async def broadcast_action(trigger: "Trigger", match: re.Match[str], room: Any) -> None:
    """Broadcast custom WebSocket message to room clients.

    Config options:
        type: Message type for the WebSocket payload (default: "custom")
        data: Data template with format placeholders for match groups

    Example trigger config:
        action: broadcast
        type: "deploy_complete"
        data: "https://{url}"
    """
    msg_type = trigger.config.get("type", "custom")
    data_template = trigger.config.get("data", "{}")
    data = data_template.format(*match.groups(), **match.groupdict())

    await room.broadcast({
        "type": msg_type,
        "data": data,
    })
