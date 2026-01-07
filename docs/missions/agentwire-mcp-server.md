# Mission: AgentWire MCP Server

> Replace say/remote-say shell scripts with proper MCP server integration for reliable voice access.

## Objective

Provide Claude Code sessions with native TTS capabilities via MCP server, eliminating installation issues and improving reliability. The MCP server runs as a background daemon and auto-detects which session is calling.

## Background

**Current say/remote-say Problems:**
- Shell scripts requiring installation and PATH configuration
- Installation issues documented in case study (~/.local/bin not in PATH)
- Depend on AGENTWIRE_ROOM env var being set correctly
- Remote machines need portal_url configured
- Portal must be running for remote-say to work
- Silent failures if portal is down
- Instruction-based (agents must "know" to use them)

**MCP Server Benefits:**
- Native tool integration (Claude Code auto-discovers)
- Always available (background daemon)
- Works without portal running (local TTS fallback)
- Auto-detects calling session (no AGENTWIRE_ROOM needed)
- Proper error messages (not silent failures)
- No installation per session (MCP configured once globally)
- No PATH issues (MCP handles routing)

## Concept

**Architecture:**
```
agentwire daemon (background service)
  ├─> MCP server (stdio protocol)
  │   └─> Tools: speak, list_voices, set_voice
  │
  ├─> Session detector
  │   └─> Maps PID → tmux session → room name
  │
  └─> TTS router (tries in order)
      ├─> Portal API (if available and session has room)
      ├─> Chatterbox direct (if configured)
      └─> System TTS (fallback)
```

**Tool definitions:**
```json
{
  "speak": {
    "description": "Speak text via TTS",
    "parameters": {
      "text": "string (required)",
      "voice": "string (optional)"
    }
  },
  "list_voices": {
    "description": "List available TTS voices",
    "returns": ["voice1", "voice2", ...]
  },
  "set_voice": {
    "description": "Set default voice for this session",
    "parameters": {
      "name": "string (required)"
    }
  }
}
```

## Wave 1: Human Actions (DECISIONS MADE)

- [x] Daemon startup: **Manual start** (user runs `agentwire daemon start`)
- [x] Fallback order: **Daemon → Portal, respecting config.yaml**
  - Use configured TTS backend (chatterbox/openai/none) as specified in config
  - Portal API used for room-specific broadcasting (if session detected)
  - Respect backend setting (don't override with fallbacks)
- [x] Scripts: **Remove say/remote-say entirely** (clean break, MCP only)
- [x] Daemon scope: **Per-user** (isolated configs, simpler permissions)

## Wave 2: Create Daemon Service

### 2.1 Daemon core implementation

**Files:** `agentwire/daemon.py` (new)

**Purpose:** Background service that runs the MCP server and handles TTS routing

**Implementation:**
```python
class AgentWireDaemon:
    """Background daemon providing MCP server and TTS routing."""

    def __init__(self):
        self.config = load_config()
        self.mcp_server = None
        self.tts_router = None
        self.session_detector = None

    async def start(self):
        """Start daemon services."""
        # Initialize session detector
        self.session_detector = SessionDetector()

        # Initialize TTS router
        self.tts_router = TTSRouter(self.config)

        # Start MCP server on stdio
        self.mcp_server = MCPServer(
            session_detector=self.session_detector,
            tts_router=self.tts_router
        )

        await self.mcp_server.run()

    async def stop(self):
        """Graceful shutdown."""
        if self.mcp_server:
            await self.mcp_server.stop()
```

**Key components:**
- Async main loop (asyncio)
- MCP server on stdio
- Session detector (PID → session mapping)
- TTS router (handles fallback logic)
- Signal handling (SIGTERM, SIGINT)

### 2.2 CLI commands for daemon control

**Files:** `agentwire/__main__.py`

**Commands:**
```bash
agentwire daemon start    # Start daemon in background
agentwire daemon stop     # Stop daemon
agentwire daemon status   # Check if running
agentwire daemon restart  # Restart daemon
agentwire daemon logs     # Show daemon logs
```

**Implementation:**
- Use subprocess to run daemon in background
- Store PID in ~/.agentwire/daemon.pid
- Logs to ~/.agentwire/logs/daemon.log
- Status checks via PID file and process lookup

## Wave 3: MCP Server Implementation

### 3.1 MCP protocol handler

**Files:** `agentwire/mcp/server.py` (new)

**Purpose:** Implement MCP server protocol over stdio

**Implementation:**
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

class AgentWireMCPServer:
    """MCP server providing TTS tools."""

    def __init__(self, session_detector, tts_router):
        self.session_detector = session_detector
        self.tts_router = tts_router
        self.server = Server("agentwire")

        # Register tools
        self.server.add_tool(
            name="speak",
            description="Speak text via TTS",
            parameters={
                "text": {"type": "string", "required": True},
                "voice": {"type": "string", "required": False}
            },
            handler=self.handle_speak
        )

        self.server.add_tool(
            name="list_voices",
            description="List available TTS voices",
            handler=self.handle_list_voices
        )

        self.server.add_tool(
            name="set_voice",
            description="Set default voice for this session",
            parameters={
                "name": {"type": "string", "required": True}
            },
            handler=self.handle_set_voice
        )

    async def handle_speak(self, text: str, voice: str = None):
        """Handle speak tool call."""
        # Detect which session is calling
        session = self.session_detector.get_calling_session()

        # Route to appropriate TTS
        result = await self.tts_router.speak(
            text=text,
            voice=voice,
            session=session
        )

        return {"success": True, "method": result.method}

    async def run(self):
        """Run MCP server on stdio."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)
```

**Dependencies:**
- Add `mcp` to pyproject.toml dependencies
- Use official Anthropic MCP SDK

### 3.2 Tool registration and discovery

**Files:** `agentwire/mcp/tools.py` (new)

**Tools to provide:**

1. **speak** - Primary TTS tool
   - Parameters: text (required), voice (optional)
   - Returns: success status and method used (portal/chatterbox/system)

2. **list_voices** - Query available voices
   - No parameters
   - Returns: Array of voice names from active TTS backend

3. **set_voice** - Set session default voice
   - Parameters: name (required)
   - Persists to rooms.json for the detected session
   - Returns: success status

## Wave 4: Session Detection

### 4.1 PID to tmux session mapper

**Files:** `agentwire/session_detector.py` (new)

**Purpose:** Auto-detect which tmux session is calling the MCP tool

**Implementation:**
```python
import os
import psutil

class SessionDetector:
    """Detect calling tmux session from process tree."""

    def get_calling_session(self) -> str | None:
        """
        Walk up process tree to find tmux session.

        Returns session name or None if not in tmux.
        """
        # Get calling process from environment
        # MCP server receives this via stdio context
        caller_pid = self._get_caller_pid()

        # Walk up process tree
        process = psutil.Process(caller_pid)
        while process.parent():
            # Check if parent is tmux
            if 'tmux' in process.name().lower():
                # Extract session name from tmux process
                return self._extract_session_name(process)
            process = process.parent()

        return None

    def _get_caller_pid(self) -> int:
        """Get PID of process that called MCP tool."""
        # MCP protocol provides this in request context
        # For now, use parent process
        return os.getppid()

    def _extract_session_name(self, tmux_process) -> str:
        """Extract session name from tmux process cmdline."""
        cmdline = tmux_process.cmdline()
        # Parse: tmux: server (myproject)
        # or: tmux attach -t myproject
        # Extract session name from args
        for i, arg in enumerate(cmdline):
            if arg == '-t' and i + 1 < len(cmdline):
                return cmdline[i + 1]

        # Try parsing from process name
        # Format: "tmux: server (session-name)"
        if '(' in tmux_process.name():
            return tmux_process.name().split('(')[1].rstrip(')')

        return None
```

**Testing:**
- Create test session: `agentwire new -s test-detection`
- Call speak tool from that session
- Verify it detects "test-detection" as calling session

### 4.2 Session to room name mapping

**Files:** `agentwire/session_detector.py`

**Purpose:** Map tmux session names to portal room names

**Logic:**
```python
def get_room_for_session(self, session_name: str) -> str:
    """
    Map session name to room name.

    Session formats:
    - "myproject" → room "myproject"
    - "myproject/branch" → room "myproject/branch"
    - "myproject@machine" → room "myproject@machine"
    - "myproject/branch@machine" → room "myproject/branch@machine"
    """
    # Session name IS the room name in AgentWire
    return session_name
```

Simple 1:1 mapping because we use consistent naming.

## Wave 5: TTS Router

### 5.1 Routing logic with fallbacks

**Files:** `agentwire/tts_router.py` (new)

**Purpose:** Route TTS requests to available backends with fallback

**Implementation:**
```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class TTSResult:
    success: bool
    method: Literal["portal", "chatterbox", "system", "none"]
    error: str | None = None

class TTSRouter:
    """Route TTS requests to available backends."""

    def __init__(self, config):
        self.config = config
        self.portal_client = PortalClient(config)
        self.chatterbox_client = ChatterboxClient(config)
        self.system_tts = SystemTTS()

    async def speak(
        self,
        text: str,
        voice: str | None,
        session: str | None
    ) -> TTSResult:
        """
        Speak text respecting config.yaml backend.

        Routing logic (Wave 1 decision):
        1. If session detected AND portal running → use portal (broadcasts to browser)
        2. Otherwise, use configured backend from config.yaml
        3. Respect user's backend choice (don't override)
        """
        # Try portal first if we have a session/room (for browser broadcasting)
        if session:
            try:
                await self.portal_client.speak(
                    text=text,
                    voice=voice,
                    room=session
                )
                return TTSResult(success=True, method="portal")
            except Exception as e:
                # Portal down or room doesn't exist, fall through to configured backend
                pass

        # Use configured TTS backend
        backend = self.config.tts.backend

        if backend == "chatterbox":
            try:
                await self.chatterbox_client.speak(
                    text=text,
                    voice=voice or self.config.tts.default_voice
                )
                return TTSResult(success=True, method="chatterbox")
            except Exception as e:
                return TTSResult(
                    success=False,
                    method="none",
                    error=f"Chatterbox failed: {e}"
                )

        elif backend == "none":
            # TTS disabled in config
            return TTSResult(success=True, method="none")

        else:
            # Unknown or unsupported backend
            return TTSResult(
                success=False,
                method="none",
                error=f"Unknown TTS backend: {backend}"
            )
```

### 5.2 Portal client

**Files:** `agentwire/tts_router.py`

**Purpose:** Send TTS requests to portal API

**Implementation:**
```python
class PortalClient:
    """Client for portal /api/say endpoint."""

    def __init__(self, config):
        self.base_url = self._get_portal_url(config)

    def _get_portal_url(self, config) -> str:
        """Get portal URL from config or portal_url file."""
        # Check ~/.agentwire/portal_url first
        portal_url_file = Path.home() / ".agentwire" / "portal_url"
        if portal_url_file.exists():
            return portal_url_file.read_text().strip()

        # Fallback to config
        host = config.server.host or "localhost"
        port = config.server.port or 8765
        return f"https://{host}:{port}"

    async def speak(self, text: str, voice: str | None, room: str):
        """Send TTS request to portal."""
        url = f"{self.base_url}/api/say/{room}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"text": text, "voice": voice},
                ssl=False  # Self-signed certs
            ) as response:
                response.raise_for_status()
                return await response.json()
```

### 5.3 Backend clients

**Files:** `agentwire/tts_router.py`

**Chatterbox client** - Direct connection to Chatterbox server (implemented in 5.2 style)

**Future backends:**
- OpenAI TTS client (for openai backend)
- ElevenLabs client (for elevenlabs backend)
- System TTS client (for system backend)

**Note:** No automatic fallbacks. If configured backend fails, return error. User controls backend via config.yaml.

## Wave 6: Installation & MCP Registration

### 6.1 Auto-install MCP server during skills install

**Files:** `agentwire/__main__.py` (cmd_skills_install)

**Changes:**
```python
def cmd_skills_install():
    """Install Claude Code skills and MCP server."""
    # ... existing skills installation ...

    # Register MCP server
    print("\nRegistering AgentWire MCP server...")
    subprocess.run([
        "claude", "mcp", "add",
        "--scope", "user",
        "agentwire",
        "agentwire", "daemon", "mcp"
    ])

    print("\nAgentWire MCP server registered!")
    print("Available tools: speak, list_voices, set_voice")
```

**Note:** `agentwire daemon mcp` is the command that runs MCP server on stdio

### 6.2 MCP command for stdio server

**Files:** `agentwire/__main__.py`

**New command:**
```bash
agentwire daemon mcp  # Run MCP server on stdio (called by Claude Code)
```

**Implementation:**
```python
async def cmd_daemon_mcp():
    """Run MCP server on stdio (called by Claude Code)."""
    # This is the entry point called by MCP
    daemon = AgentWireDaemon()
    await daemon.start_mcp_only()  # Just MCP, not full daemon
```

### 6.3 Remove say/remote-say scripts

**Files:** `agentwire/scripts/say`, `agentwire/scripts/remote-say`, `agentwire/__main__.py`, `pyproject.toml`

**Removal strategy (Wave 1 decision - clean break):**
- Delete `agentwire/scripts/say` and `agentwire/scripts/remote-say`
- Remove from `pyproject.toml` artifacts
- Remove installation logic from `cmd_skills_install`
- Update docs to only mention MCP tools

**Migration path for users:**
- Existing instructions that use `say "text"` should be updated to use MCP `speak` tool
- Claude Code auto-discovers speak tool, no instruction changes needed in practice
- If users have custom scripts calling say/remote-say, they'll get "command not found" and need to update

## Wave 7: Testing

### 7.1 Unit tests

**Files:** `tests/test_mcp_server.py` (new)

**Tests:**
- MCP tool registration
- Session detection from PID
- TTS routing with fallbacks
- Error handling

### 7.2 Integration tests

**Files:** `tests/test_daemon.py` (new)

**Tests:**
- Daemon start/stop/restart
- MCP server responds on stdio
- speak tool from Claude Code session
- Fallback behavior (portal down → chatterbox → system)

### 7.3 Manual testing

**Scenarios:**
1. Start daemon: `agentwire daemon start`
2. Create session: `agentwire new -s test-mcp`
3. In Claude Code, use speak tool: "Use the speak tool to say hello"
4. Verify TTS plays
5. Stop portal: `agentwire portal stop`
6. Try speak again, verify fallback works
7. Check logs: `agentwire daemon logs`

## Wave 8: Documentation

### 8.1 Update CLAUDE.md

**Files:** `CLAUDE.md`

**Add section:**
```markdown
## Voice Layer

AgentWire provides TTS via MCP server (no installation needed per session).

**Available MCP tools:**
- `speak(text, voice=None)` - Speak text via TTS
- `list_voices()` - List available voices
- `set_voice(name)` - Set default voice for session

**Setup:**
```bash
agentwire skills install  # Registers MCP server
agentwire daemon start    # Start background daemon
```

**How it works:**
- Daemon auto-detects calling session
- Routes to portal API (if room exists)
- Fallback to Chatterbox or system TTS
- No AGENTWIRE_ROOM env var needed

**Deprecation:** say/remote-say scripts are deprecated. Use MCP tools instead.
```

### 8.2 Update README.md

**Files:** `README.md`

**Update Voice section:**
```markdown
## Voice Integration

AgentWire provides native voice capabilities to Claude Code via MCP:

```bash
# One-time setup
agentwire skills install  # Registers MCP server

# Start daemon (provides TTS routing)
agentwire daemon start

# Now all Claude sessions can use:
# - speak(text, voice=None)
# - list_voices()
# - set_voice(name)
```

The daemon auto-detects which session is calling and routes TTS appropriately.
```

### 8.3 Migration guide

**Files:** `docs/MIGRATION-MCP.md` (new)

**Content:**
- Explain deprecation of say/remote-say
- Show how to use MCP tools instead
- Benefits of MCP approach
- Troubleshooting (daemon not running, session detection fails)

## Completion Criteria

- [ ] Daemon service implemented and tested
- [ ] MCP server provides speak, list_voices, set_voice tools
- [ ] Session detection works (PID → tmux → room)
- [ ] TTS routing with fallbacks (portal → chatterbox → system)
- [ ] CLI commands: daemon start/stop/status/restart/logs
- [ ] MCP server auto-registers during skills install
- [ ] Deprecation warnings added to say/remote-say scripts
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing complete (all scenarios)
- [ ] Documentation updated (CLAUDE.md, README.md, migration guide)

## Technical Notes

**MCP Protocol:**
- Uses stdio transport (Claude Code requirement)
- JSON-RPC 2.0 based
- Tools are discoverable via list_tools
- Official Anthropic MCP SDK handles protocol details

**Session Detection Edge Cases:**
- Process not in tmux → return None, use system TTS only
- Session name with special chars → handle encoding
- Multiple Claude sessions in same tmux → works (PID is unique)

**Fallback Behavior:**
- Portal unreachable → try next method immediately
- Chatterbox timeout → try next after 3s
- System TTS unavailable → return error with clear message

**Daemon Lifecycle:**
- Start: Background process, logs to ~/.agentwire/logs/daemon.log
- Stop: Graceful shutdown via SIGTERM
- Restart: Stop then start
- Status: Check PID file and process exists
- Logs: Tail daemon.log

**Performance:**
- MCP adds ~50ms overhead (negligible)
- Session detection cached for 60s per process
- Portal/Chatterbox clients reuse connections

## Migration Notes

**Existing users:**
- say/remote-say scripts keep working (deprecated but functional)
- No breaking changes
- Install new daemon: `agentwire skills install && agentwire daemon start`
- Gradually migrate to MCP tools

**Benefits over scripts:**
- No PATH issues
- No AGENTWIRE_ROOM env var needed
- Works without portal running
- Better error messages
- Auto-discovered by Claude Code
