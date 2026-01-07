"""AgentWire daemon - background service providing MCP server and TTS routing."""

import asyncio
import signal
import sys
from pathlib import Path

from .config import load_config


class AgentWireDaemon:
    """Background daemon providing MCP server and TTS routing."""

    def __init__(self):
        """Initialize daemon with config and components."""
        self.config = load_config()
        self.mcp_server = None
        self.tts_router = None
        self.session_detector = None
        self._shutdown = False

    async def start(self):
        """Start daemon services."""
        print("Starting AgentWire daemon...", file=sys.stderr)

        # Import components (will be created by other agents)
        from .session_detector import SessionDetector
        from .tts_router import TTSRouter
        from .mcp.server import MCPServer

        # Initialize session detector
        self.session_detector = SessionDetector()
        print("Session detector initialized", file=sys.stderr)

        # Initialize TTS router
        self.tts_router = TTSRouter(self.config)
        print("TTS router initialized", file=sys.stderr)

        # Start MCP server on stdio
        self.mcp_server = MCPServer(
            session_detector=self.session_detector,
            tts_router=self.tts_router,
        )
        print("MCP server initialized", file=sys.stderr)

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        print("AgentWire daemon started", file=sys.stderr)

        # Run MCP server (blocks until stopped)
        await self.mcp_server.run()

    async def stop(self):
        """Graceful shutdown."""
        if self._shutdown:
            return
        self._shutdown = True

        print("\nShutting down AgentWire daemon...", file=sys.stderr)

        if self.mcp_server:
            await self.mcp_server.stop()

        print("AgentWire daemon stopped", file=sys.stderr)


async def main():
    """Main entry point for daemon."""
    daemon = AgentWireDaemon()
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())
