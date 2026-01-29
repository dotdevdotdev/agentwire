"""AgentWire MCP Server.

Exposes AgentWire capabilities as MCP tools for external agents.
This allows tools like MoltBot, Claude Desktop, etc. to manage
tmux sessions, remote machines, and voice features.

Usage:
    agentwire mcp  # Starts MCP server on stdio
"""

import base64
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (stdout is reserved for MCP JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("agentwire-mcp")

# Initialize FastMCP server
mcp = FastMCP(
    name="agentwire",
    instructions="AgentWire MCP server for terminal session management, remote machines, and voice interface for AI agents.",
)


# =============================================================================
# Configuration
# =============================================================================


def get_portal_url() -> str:
    """Get portal URL from environment or config.

    Resolution order:
    1. AGENTWIRE_PORTAL_URL env var
    2. ~/.agentwire/config.yaml → portal.url
    3. Default: https://localhost:8765
    """
    # 1. Environment variable
    if url := os.environ.get("AGENTWIRE_PORTAL_URL"):
        return url

    # 2. Config file
    config_path = Path.home() / ".agentwire" / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
                if url := config.get("portal", {}).get("url"):
                    return url
        except Exception as e:
            logger.warning(f"Failed to read config: {e}")

    # 3. Default
    return "https://localhost:8765"


# =============================================================================
# CLI Helpers
# =============================================================================


def run_agentwire_cmd(
    args: list[str],
    json_output: bool = True,
    timeout: int = 30,
) -> dict:
    """Run agentwire CLI command and return result.

    Args:
        args: Command arguments (e.g., ["list", "--sessions"])
        json_output: Whether to add --json flag and parse output
        timeout: Command timeout in seconds (default: 30)

    Returns:
        Dict with 'success', 'output', and possibly other fields from JSON output.
        For JSON responses without 'success' field, wraps data with success=True.
    """
    cmd = ["agentwire"] + args
    if json_output:
        cmd.append("--json")

    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Try to parse JSON output
        if json_output and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                # If the response is valid JSON but doesn't have 'success',
                # wrap it with success based on return code
                if "success" not in data:
                    return {
                        "success": result.returncode == 0,
                        **data,
                    }
                return data
            except json.JSONDecodeError:
                pass

        # Fall back to raw output
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else None,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "agentwire command not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_sessions(data: dict) -> str:
    """Format sessions list for LLM consumption."""
    sessions = data.get("sessions", [])
    if not sessions:
        return "No active sessions."

    lines = ["Active sessions:"]
    for s in sessions:
        machine = s.get("machine") or "local"
        name = s.get("name", "unknown")
        windows = s.get("windows", 1)
        path = s.get("path", "")
        session_type = s.get("type", "unknown")
        lines.append(f"  - {name} ({machine}): {windows} window(s), type={session_type}, path={path}")

    return "\n".join(lines)


def format_panes(data: dict) -> str:
    """Format panes list for LLM consumption."""
    panes = data.get("panes", [])
    session = data.get("session", "unknown")

    if not panes:
        return f"No panes in session '{session}'."

    lines = [f"Panes in session '{session}':"]
    for p in panes:
        idx = p.get("index", 0)
        cmd = p.get("command", "unknown")
        active = " (active)" if p.get("active") else ""
        role = "orchestrator" if idx == 0 else "worker"
        lines.append(f"  - Pane {idx} [{role}]: {cmd}{active}")

    return "\n".join(lines)


def format_machines(data: dict) -> str:
    """Format machines list for LLM consumption."""
    machines = data.get("machines", [])
    if not machines:
        return "No remote machines configured."

    lines = ["Configured machines:"]
    for m in machines:
        mid = m.get("id", "unknown")
        host = m.get("host", "unknown")
        user = m.get("user", "")
        status = m.get("status", "unknown")
        user_str = f"{user}@" if user else ""
        lines.append(f"  - {mid}: {user_str}{host} (status: {status})")

    return "\n".join(lines)


def format_projects(data: dict) -> str:
    """Format projects list for LLM consumption."""
    projects = data.get("projects", [])
    if not projects:
        return "No projects found."

    lines = ["Available projects:"]
    for p in projects:
        name = p.get("name", "unknown")
        path = p.get("path", "")
        has_config = p.get("has_config", False)
        config_marker = " (has .agentwire.yml)" if has_config else ""
        lines.append(f"  - {name}: {path}{config_marker}")

    return "\n".join(lines)


def format_roles(data: dict) -> str:
    """Format roles list for LLM consumption."""
    roles = data.get("roles", [])
    if not roles:
        return "No roles available."

    lines = ["Available roles:"]
    for r in roles:
        name = r.get("name", "unknown")
        desc = r.get("description", "")
        source = r.get("source", "")
        lines.append(f"  - {name}: {desc} ({source})")

    return "\n".join(lines)


def format_voices(data: dict) -> str:
    """Format voices list for LLM consumption."""
    voices = data.get("voices", [])
    if not voices:
        return "No custom voices available. Default voice will be used."

    lines = ["Available voices:"]
    for v in voices:
        name = v.get("name", "unknown") if isinstance(v, dict) else v
        lines.append(f"  - {name}")

    return "\n".join(lines)


# =============================================================================
# Session Management Tools
# =============================================================================


@mcp.tool()
def sessions_list() -> str:
    """List all active AgentWire sessions.

    Returns information about all tmux sessions including name, machine,
    window count, working directory, and session type.
    """
    data = run_agentwire_cmd(["list", "--sessions"])
    if not data.get("success"):
        return f"Failed to list sessions: {data.get('error', 'Unknown error')}"
    return format_sessions(data)


@mcp.tool()
def session_create(
    name: str,
    project_dir: str | None = None,
    roles: str | None = None,
    session_type: str | None = None,
) -> str:
    """Create a new AgentWire session.

    Args:
        name: Session name (required)
        project_dir: Project directory path (optional)
        roles: Comma-separated list of roles to apply (optional)
        session_type: Session type like 'claude-bypass', 'opencode-bypass' (optional)

    Returns:
        Success message or error description.
    """
    args = ["new", "-s", name]

    if project_dir:
        args.extend(["-p", project_dir])
    if roles:
        args.extend(["--roles", roles])
    if session_type:
        args.extend(["--type", session_type])

    data = run_agentwire_cmd(args)
    if data.get("success"):
        return f"Session '{name}' created successfully."
    return f"Failed to create session: {data.get('error', 'Unknown error')}"


@mcp.tool()
def session_send(session: str, message: str) -> str:
    """Send a prompt/message to a session.

    Args:
        session: Session name (can include @machine suffix for remote)
        message: The message to send (Enter key is appended automatically)

    Returns:
        Success message or error description.
    """
    args = ["send", "-s", session, message]
    data = run_agentwire_cmd(args)
    if data.get("success"):
        return f"Message sent to session '{session}'."
    return f"Failed to send message: {data.get('error', 'Unknown error')}"


@mcp.tool()
def session_output(session: str, lines: int = 50) -> str:
    """Capture output from a session.

    Args:
        session: Session name (can include @machine suffix for remote)
        lines: Number of lines to capture (default: 50)

    Returns:
        The captured output from the session.
    """
    args = ["output", "-s", session, "-n", str(lines)]
    data = run_agentwire_cmd(args)
    if data.get("success"):
        return data.get("output", "")
    return f"Failed to capture output: {data.get('error', 'Unknown error')}"


@mcp.tool()
def session_info(session: str) -> str:
    """Get detailed information about a session.

    Args:
        session: Session name (can include @machine suffix for remote)

    Returns:
        Session metadata including working directory, pane count, etc.
    """
    args = ["info", "-s", session]
    data = run_agentwire_cmd(args)
    if not data.get("success"):
        return f"Failed to get session info: {data.get('error', 'Unknown error')}"

    # Format the info nicely
    lines = [f"Session: {session}"]
    if cwd := data.get("cwd"):
        lines.append(f"  Working directory: {cwd}")
    if panes := data.get("panes"):
        lines.append(f"  Panes: {len(panes)}")
    if session_type := data.get("type"):
        lines.append(f"  Type: {session_type}")
    if roles := data.get("roles"):
        lines.append(f"  Roles: {', '.join(roles)}")

    return "\n".join(lines)


@mcp.tool()
def session_kill(session: str) -> str:
    """Terminate a session.

    Args:
        session: Session name (can include @machine suffix for remote)

    Returns:
        Success message or error description.
    """
    args = ["kill", "-s", session]
    data = run_agentwire_cmd(args)
    if data.get("success"):
        return f"Session '{session}' terminated."
    return f"Failed to kill session: {data.get('error', 'Unknown error')}"


# =============================================================================
# Pane Management Tools
# =============================================================================


@mcp.tool()
def pane_spawn(
    session: str | None = None,
    roles: str | None = None,
    pane_type: str | None = None,
) -> str:
    """Spawn a worker pane in a session.

    Args:
        session: Session name (defaults to current session if in tmux)
        roles: Comma-separated list of roles for the worker
        pane_type: Session type like 'opencode-bypass' (optional)

    Returns:
        Pane index of the spawned worker or error description.
    """
    args = ["spawn"]

    if session:
        args.extend(["-s", session])
    if roles:
        args.extend(["--roles", roles])
    if pane_type:
        args.extend(["--type", pane_type])

    # Spawn can take a while to initialize the agent, use longer timeout
    data = run_agentwire_cmd(args, timeout=120)
    if data.get("success"):
        pane_idx = data.get("pane_index", data.get("pane", "?"))
        return f"Worker pane {pane_idx} spawned successfully."
    return f"Failed to spawn pane: {data.get('error', 'Unknown error')}"


@mcp.tool()
def pane_send(pane: int, message: str, session: str | None = None) -> str:
    """Send a message to a specific pane.

    Args:
        pane: Pane index (0 = orchestrator, 1+ = workers)
        message: The message to send
        session: Session name (defaults to current session if in tmux)

    Returns:
        Success message or error description.
    """
    args = ["send", "--pane", str(pane), message]
    if session:
        args.extend(["-s", session])

    data = run_agentwire_cmd(args)
    if data.get("success"):
        return f"Message sent to pane {pane}."
    return f"Failed to send to pane: {data.get('error', 'Unknown error')}"


@mcp.tool()
def pane_output(pane: int, session: str | None = None, lines: int = 50) -> str:
    """Capture output from a specific pane.

    Args:
        pane: Pane index
        session: Session name (defaults to current session if in tmux)
        lines: Number of lines to capture (default: 50)

    Returns:
        The captured output from the pane.
    """
    args = ["output", "--pane", str(pane), "-n", str(lines)]
    if session:
        args.extend(["-s", session])

    data = run_agentwire_cmd(args)
    if data.get("success"):
        return data.get("output", "")
    return f"Failed to capture pane output: {data.get('error', 'Unknown error')}"


@mcp.tool()
def pane_kill(pane: int, session: str | None = None) -> str:
    """Kill a specific pane.

    Args:
        pane: Pane index to kill
        session: Session name (defaults to current session if in tmux)

    Returns:
        Success message or error description.
    """
    args = ["kill", "--pane", str(pane)]
    if session:
        args.extend(["-s", session])

    data = run_agentwire_cmd(args)
    if data.get("success"):
        return f"Pane {pane} terminated."
    return f"Failed to kill pane: {data.get('error', 'Unknown error')}"


@mcp.tool()
def panes_list(session: str | None = None) -> str:
    """List panes in a session.

    Args:
        session: Session name (defaults to current session if in tmux)

    Returns:
        List of panes with their indices, commands, and status.
    """
    # Use 'info' command which returns pane information
    args = ["info"]
    if session:
        args.extend(["-s", session])

    data = run_agentwire_cmd(args)
    if not data.get("success"):
        return f"Failed to list panes: {data.get('error', 'Unknown error')}"

    # Extract panes from info response
    panes = data.get("panes", [])
    session_name = session or data.get("session", "current")

    if not panes:
        return f"No panes found in session '{session_name}'."

    lines = [f"Panes in session '{session_name}':"]
    for p in panes:
        idx = p.get("index", 0)
        cmd = p.get("command", "unknown")
        active = " (active)" if p.get("active") else ""
        role = "orchestrator" if idx == 0 else "worker"
        lines.append(f"  - Pane {idx} [{role}]: {cmd}{active}")

    return "\n".join(lines)


# =============================================================================
# Machine Management Tools
# =============================================================================


@mcp.tool()
def machines_list() -> str:
    """List all configured remote machines.

    Returns:
        List of machines with their connection details and status.
    """
    data = run_agentwire_cmd(["machine", "list"])
    if not data.get("success"):
        return f"Failed to list machines: {data.get('error', 'Unknown error')}"
    return format_machines(data)


@mcp.tool()
def machine_add(machine_id: str, host: str, user: str, port: int = 22) -> str:
    """Add a new remote machine.

    Args:
        machine_id: Unique identifier for the machine
        host: Hostname or IP address
        user: SSH username
        port: SSH port (default: 22)

    Returns:
        Success message or error description.
    """
    args = ["machine", "add", machine_id, "--host", host, "--user", user]
    if port != 22:
        args.extend(["--port", str(port)])

    # machine add doesn't support --json
    data = run_agentwire_cmd(args, json_output=False)
    if data.get("success"):
        return f"Machine '{machine_id}' added successfully."
    return f"Failed to add machine: {data.get('error', 'Unknown error')}"


@mcp.tool()
def machine_remove(machine_id: str) -> str:
    """Remove a remote machine.

    Args:
        machine_id: Machine identifier to remove

    Returns:
        Success message or error description.
    """
    args = ["machine", "remove", machine_id]
    # machine remove doesn't support --json
    data = run_agentwire_cmd(args, json_output=False)
    if data.get("success"):
        return f"Machine '{machine_id}' removed."
    return f"Failed to remove machine: {data.get('error', 'Unknown error')}"


# =============================================================================
# Voice Tools (TTS/STT)
# =============================================================================


@mcp.tool()
def say(text: str, session: str | None = None, voice: str | None = None) -> str:
    """Speak text via TTS.

    Audio routes to the browser portal if connected, otherwise local speakers.

    Args:
        text: Text to speak
        session: Target session for audio routing (optional)
        voice: Voice name to use (optional, uses default if not specified)

    Returns:
        Success message or error description.
    """
    args = ["say"]
    if session:
        args.extend(["-s", session])
    if voice:
        args.extend(["--voice", voice])
    args.append(text)

    # Say command doesn't return JSON, run without --json
    data = run_agentwire_cmd(args, json_output=False)
    if data.get("success"):
        return "Text queued for speech."
    return f"Failed to speak: {data.get('error', 'Unknown error')}"


@mcp.tool()
def alert(text: str, to: str | None = None) -> str:
    """Send a text notification (no audio).

    Notifications appear in the target session/portal without voice.

    Args:
        text: Notification text
        to: Target session name (optional)

    Returns:
        Success message or error description.
    """
    args = ["alert"]
    if to:
        args.extend(["--to", to])
    args.append(text)

    data = run_agentwire_cmd(args, json_output=False)
    if data.get("success"):
        return "Alert sent."
    return f"Failed to send alert: {data.get('error', 'Unknown error')}"


@mcp.tool()
def listen_start() -> str:
    """Start voice recording.

    Begins recording audio for speech-to-text transcription.
    Call listen_stop() to stop and get the transcript.

    Returns:
        Success message or error description.
    """
    data = run_agentwire_cmd(["listen", "start"], json_output=False)
    if data.get("success"):
        return "Recording started."
    return f"Failed to start recording: {data.get('error', 'Unknown error')}"


@mcp.tool()
def listen_stop() -> str:
    """Stop recording and get transcript.

    Stops the current recording and transcribes the audio.

    Returns:
        The transcribed text or error description.
    """
    # listen stop doesn't support --json, run without it
    data = run_agentwire_cmd(["listen", "stop"], json_output=False)
    if data.get("success"):
        return data.get("output", "Recording stopped.")
    return f"Failed to stop recording: {data.get('error', 'Unknown error')}"


@mcp.tool()
def transcribe(audio_base64: str, format: str = "webm") -> str:
    """Transcribe audio to text.

    Accepts base64-encoded audio data and returns the transcribed text.
    This is useful for external agents that have their own audio capture
    or want to process pre-recorded audio files.

    Args:
        audio_base64: Base64-encoded audio data
        format: Audio format - webm, wav, mp3, ogg, m4a (default: webm)

    Returns:
        Transcribed text or error description.
    """
    import requests
    import urllib3

    # Suppress SSL warnings for self-signed certs
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Decode base64 audio
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as e:
        return f"Failed to decode base64 audio: {e}"

    if not audio_bytes:
        return "Empty audio data"

    # Determine MIME type
    mime_types = {
        "webm": "audio/webm",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "m4a": "audio/m4a",
    }
    mime_type = mime_types.get(format.lower(), "audio/webm")

    # POST to portal's /transcribe endpoint
    portal_url = get_portal_url()
    url = f"{portal_url}/transcribe"

    try:
        # Create multipart form data
        files = {"audio": (f"audio.{format}", audio_bytes, mime_type)}
        response = requests.post(url, files=files, verify=False, timeout=60)

        if response.status_code != 200:
            return f"Transcription request failed: HTTP {response.status_code}"

        data = response.json()
        if "error" in data:
            return f"Transcription failed: {data['error']}"

        return data.get("text", "")

    except requests.exceptions.ConnectionError:
        return "Failed to connect to portal. Is it running? (agentwire portal status)"
    except Exception as e:
        return f"Transcription failed: {e}"


@mcp.tool()
def voices_list() -> str:
    """List available TTS voices.

    Returns:
        List of voice names that can be used with the say() tool.
    """
    data = run_agentwire_cmd(["voiceclone", "list"])
    if not data.get("success"):
        return f"Failed to list voices: {data.get('error', 'Unknown error')}"
    return format_voices(data)


# =============================================================================
# Projects & Roles Tools
# =============================================================================


@mcp.tool()
def projects_list() -> str:
    """Discover available projects.

    Scans the configured projects directory for projects that can
    be used to create new sessions.

    Returns:
        List of projects with their paths and configuration status.
    """
    data = run_agentwire_cmd(["projects", "list"])
    if not data.get("success"):
        return f"Failed to list projects: {data.get('error', 'Unknown error')}"
    return format_projects(data)


@mcp.tool()
def roles_list() -> str:
    """List available roles.

    Roles define agent behavior and capabilities. They can be applied
    when creating sessions or spawning workers.

    Returns:
        List of roles with their descriptions.
    """
    data = run_agentwire_cmd(["roles", "list"])
    if not data.get("success"):
        return f"Failed to list roles: {data.get('error', 'Unknown error')}"
    return format_roles(data)


@mcp.tool()
def role_show(name: str) -> str:
    """Get detailed information about a role.

    Args:
        name: Role name to look up

    Returns:
        Role details including description, tools, and instructions.
    """
    data = run_agentwire_cmd(["roles", "show", name])
    if not data.get("success"):
        return f"Failed to show role: {data.get('error', 'Unknown error')}"

    lines = [f"Role: {name}"]
    if desc := data.get("description"):
        lines.append(f"  Description: {desc}")
    if tools := data.get("tools"):
        lines.append(f"  Tools: {', '.join(tools)}")
    if model := data.get("model"):
        lines.append(f"  Model: {model}")
    if instructions := data.get("instructions"):
        # Truncate long instructions
        preview = instructions[:200] + "..." if len(instructions) > 200 else instructions
        lines.append(f"  Instructions: {preview}")

    return "\n".join(lines)


# =============================================================================
# Status Tools
# =============================================================================


@mcp.tool()
def portal_status() -> str:
    """Check portal server health.

    Returns:
        Portal status including whether it's running and on what port.
    """
    data = run_agentwire_cmd(["portal", "status"])
    if data.get("success"):
        running = data.get("running", False)
        url = data.get("url", get_portal_url())
        if running:
            return f"Portal is running at {url}"
        return "Portal is not running. Start with 'agentwire portal start'."
    return f"Failed to check portal status: {data.get('error', 'Unknown error')}"


@mcp.tool()
def tts_status() -> str:
    """Check TTS server status.

    Returns:
        TTS server status and configuration.
    """
    data = run_agentwire_cmd(["tts", "status"])
    if data.get("success"):
        running = data.get("running", False)
        backend = data.get("backend", "unknown")
        if running:
            return f"TTS server is running (backend: {backend})"
        return f"TTS server is not running. Backend configured: {backend}"
    return f"Failed to check TTS status: {data.get('error', 'Unknown error')}"


@mcp.tool()
def stt_status() -> str:
    """Check STT server status.

    Returns:
        STT server status and configuration.
    """
    data = run_agentwire_cmd(["stt", "status"])
    if data.get("success"):
        running = data.get("running", False)
        if running:
            return "STT server is running."
        return "STT server is not running."
    return f"Failed to check STT status: {data.get('error', 'Unknown error')}"


# =============================================================================
# Server Entry Point
# =============================================================================


def run_server():
    """Run the MCP server on stdio transport."""
    logger.info("Starting AgentWire MCP server")
    logger.info(f"Portal URL: {get_portal_url()}")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
