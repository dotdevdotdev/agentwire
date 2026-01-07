"""MCP tool definitions and schemas for AgentWire."""

from typing import Any

# Tool schemas following MCP protocol format
TOOL_SPEAK = {
    "name": "speak",
    "description": "Speak text via TTS. Routes to portal API for browser playback if session detected, otherwise uses configured TTS backend.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to speak via TTS",
            },
            "voice": {
                "type": "string",
                "description": "Voice name to use (optional). If not specified, uses session's default voice from rooms.json or config default.",
            },
        },
        "required": ["text"],
    },
}

TOOL_LIST_VOICES = {
    "name": "list_voices",
    "description": "List all available TTS voices from the active TTS backend",
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
}

TOOL_SET_VOICE = {
    "name": "set_voice",
    "description": "Set the default TTS voice for the current session. Persists to rooms.json.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The voice name to set as default for this session",
            },
        },
        "required": ["name"],
    },
}


def get_all_tools() -> list[dict[str, Any]]:
    """Get all tool definitions."""
    return [TOOL_SPEAK, TOOL_LIST_VOICES, TOOL_SET_VOICE]
