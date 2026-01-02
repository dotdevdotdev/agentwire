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


@default_registry.handler("tts")
async def tts_action(trigger: "Trigger", match: re.Match[str], room: Any) -> None:
    """Speak text via TTS and broadcast audio to room clients.

    Migrated from server.py _say_to_room() / speak() methods.
    The room.speak() method handles TTS generation with configured voice
    and broadcasts base64-encoded audio to connected clients.

    Config options:
        template: Format string with placeholders for match groups
                  Defaults to "{0}" (first capturing group)

    Example trigger configs:
        # Simple say command detection
        pattern: 'say\\s+"([^"]+)"'
        action: tts
        # Uses first capture group by default

        # Custom template
        pattern: 'All (?P<count>\\d+) tests? passed'
        action: tts
        template: "{count} tests passed!"
    """
    template = trigger.config.get("template")

    if template:
        # Format template with named and positional groups
        try:
            text = template.format(*match.groups(), **match.groupdict())
        except (IndexError, KeyError):
            # Fallback if template formatting fails
            text = match.group(1) if match.lastindex else match.group(0)
    else:
        # No template: use first capturing group or full match
        text = match.group(1) if match.lastindex else match.group(0)

    if not text or not text.strip():
        return

    await room.speak(text.strip())


@default_registry.handler("sound")
async def sound_action(trigger: "Trigger", match: re.Match[str], room: Any) -> None:
    """Play a sound effect on connected clients.

    Broadcasts a 'sound' event to room clients, which play the sound
    via browser Audio API.

    Config options:
        sound: Name of sound to play (default: "notification")
               Available: success, error, notification, done

    Example trigger configs:
        # Play error sound on build failure
        pattern: 'BUILD FAILED'
        action: sound
        sound: error

        # Play success on test pass
        pattern: 'All tests passed'
        action: sound
        sound: success
    """
    sound_name = trigger.config.get("sound", "notification")

    await room.broadcast({
        "type": "sound",
        "sound": sound_name,
    })


@default_registry.handler("popup")
async def popup_action(trigger: "Trigger", match: re.Match[str], room: Any) -> None:
    """Show popup modal in browser clients for AskUserQuestion prompts.

    Migrated from server.py ASK_PATTERN detection and _parse_ask_options().
    Broadcasts a 'question' event with header, question text, and parsed options.
    Also speaks the question via TTS.

    Expected match groups (by name or position):
        1. header: The question header/title (e.g., "Confirm Action")
        2. question: The question text ending with ? (e.g., "Do you want to proceed?")
        3. options_block: Raw text containing numbered options in format:
           ❯ 1. Label
                Description
             2. Label
                Description

    The room.broadcast() method sends the question event to clients.
    The room.speak() method reads the question aloud.
    """
    # Extract components - try named groups first, fall back to positional
    header = _safe_group(match, "header", 1)
    question = _safe_group(match, "question", 2)
    options_block = _safe_group(match, "options_block", 3)

    if not question:
        return

    # Parse options from the options block
    options = _parse_ask_options(options_block) if options_block else []

    # Broadcast question to room
    await room.broadcast({
        "type": "question",
        "header": header.strip() if header else "",
        "question": question.strip(),
        "options": options,
    })

    # Also speak the question via TTS
    tts_text = question.strip() + ". "
    for opt in options:
        label = opt.get("label", "")
        if label and label != "Type something.":
            tts_text += f"{opt.get('number', '')}: {label}. "

    await room.speak(tts_text)


def _safe_group(match: re.Match[str], name: str, index: int) -> str:
    """Safely extract a group from match by name or index.

    Args:
        match: The regex match object
        name: Named group to try first
        index: Positional index to fall back to

    Returns:
        The group value or empty string if not found
    """
    try:
        return match.group(name) or ""
    except (IndexError, re.error):
        pass
    try:
        if match.lastindex and match.lastindex >= index:
            return match.group(index) or ""
    except (IndexError, re.error):
        pass
    return ""


def _parse_ask_options(options_block: str) -> list[dict]:
    """Parse numbered options from AskUserQuestion block.

    Migrated from server.py _parse_ask_options() method.

    Args:
        options_block: Raw text containing options in format:
            ❯ 1. Label
                 Description
               2. Label
                 Description

    Returns:
        List of {number, label, description} dicts.
    """
    # Pattern to strip ANSI escape codes
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*m|\x1b\].*?\x07')

    options: list[dict] = []
    current_option: dict | None = None

    for line in options_block.split('\n'):
        # Strip ANSI codes
        line = ansi_pattern.sub('', line)

        # Match numbered option: "❯ 1. Label" or "  2. Label"
        option_match = re.match(r'[❯\s]*(\d+)\.\s+(.+)', line)
        if option_match:
            if current_option:
                options.append(current_option)
            current_option = {
                'number': int(option_match.group(1)),
                'label': option_match.group(2).strip(),
                'description': '',
            }
        elif current_option and line.strip():
            # Description line (indented)
            current_option['description'] = line.strip()

    if current_option:
        options.append(current_option)

    return options
