"""MCP server protocol handler for AgentWire."""

import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tools import TOOL_SPEAK, TOOL_LIST_VOICES, TOOL_SET_VOICE

logger = logging.getLogger(__name__)


class AgentWireMCPServer:
    """MCP server providing TTS tools via stdio protocol."""

    def __init__(self, session_detector, tts_router):
        """
        Initialize MCP server.

        Args:
            session_detector: SessionDetector instance for auto-detecting calling session
            tts_router: TTSRouter instance for routing TTS requests
        """
        self.session_detector = session_detector
        self.tts_router = tts_router
        self.server = Server("agentwire")

        # Register list_tools handler
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name=TOOL_SPEAK["name"],
                    description=TOOL_SPEAK["description"],
                    inputSchema=TOOL_SPEAK["inputSchema"],
                ),
                Tool(
                    name=TOOL_LIST_VOICES["name"],
                    description=TOOL_LIST_VOICES["description"],
                    inputSchema=TOOL_LIST_VOICES["inputSchema"],
                ),
                Tool(
                    name=TOOL_SET_VOICE["name"],
                    description=TOOL_SET_VOICE["description"],
                    inputSchema=TOOL_SET_VOICE["inputSchema"],
                ),
            ]

        # Register call_tool handler
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls."""
            if name == "speak":
                return await self.handle_speak(arguments)
            elif name == "list_voices":
                return await self.handle_list_voices(arguments)
            elif name == "set_voice":
                return await self.handle_set_voice(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def handle_speak(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Handle speak tool call.

        Args:
            arguments: Tool arguments with 'text' (required) and 'voice' (optional)

        Returns:
            List containing a TextContent with success status and method used
        """
        text = arguments.get("text")
        if not text:
            return [TextContent(type="text", text="Error: text parameter is required")]

        voice = arguments.get("voice")

        # Detect calling session
        session = self.session_detector.get_calling_session()
        logger.info(f"speak called from session: {session}")

        # Route TTS request
        result = await self.tts_router.speak(text=text, voice=voice, session=session)

        if result.success:
            return [
                TextContent(
                    type="text",
                    text=f"Spoke via {result.method}: {text[:50]}{'...' if len(text) > 50 else ''}",
                )
            ]
        else:
            error_msg = result.error or "Unknown error"
            return [TextContent(type="text", text=f"Error: {error_msg}")]

    async def handle_list_voices(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Handle list_voices tool call.

        Returns:
            List containing a TextContent with available voice names
        """
        voices = await self.tts_router.list_voices()
        voice_list = ", ".join(voices)
        return [TextContent(type="text", text=f"Available voices: {voice_list}")]

    async def handle_set_voice(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Handle set_voice tool call.

        Args:
            arguments: Tool arguments with 'name' (required)

        Returns:
            List containing a TextContent with success status
        """
        name = arguments.get("name")
        if not name:
            return [TextContent(type="text", text="Error: name parameter is required")]

        # Detect calling session
        session = self.session_detector.get_calling_session()
        if not session:
            return [
                TextContent(
                    type="text",
                    text="Error: Could not detect session. set_voice requires running inside a tmux session.",
                )
            ]

        # Set voice for session
        success = await self.tts_router.set_voice(session=session, voice=name)

        if success:
            return [
                TextContent(
                    type="text", text=f"Set voice to '{name}' for session '{session}'"
                )
            ]
        else:
            return [
                TextContent(type="text", text=f"Error: Failed to set voice to '{name}'")
            ]

    async def run(self):
        """Run MCP server on stdio."""
        logger.info("Starting AgentWire MCP server on stdio")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )
