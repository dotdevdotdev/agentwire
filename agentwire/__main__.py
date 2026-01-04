"""CLI entry point for AgentWire."""

import argparse
import datetime
import importlib.resources
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .worktree import parse_session_name, get_session_path, ensure_worktree, remove_worktree

# Default config directory
CONFIG_DIR = Path.home() / ".agentwire"


def generate_certs() -> int:
    """Generate self-signed SSL certificates."""
    cert_dir = CONFIG_DIR
    cert_dir.mkdir(parents=True, exist_ok=True)

    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        print(f"Certificates already exist at {cert_dir}")
        response = input("Overwrite? [y/N] ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 1

    print(f"Generating self-signed certificates in {cert_dir}...")

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate certificates: {e.stderr}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("openssl not found. Please install OpenSSL.", file=sys.stderr)
        return 1

    print(f"Created: {cert_path}")
    print(f"Created: {key_path}")
    return 0


def tmux_session_exists(name: str) -> bool:
    """Check if a tmux session exists (exact match)."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={name}"],  # = prefix for exact match
        capture_output=True,
    )
    return result.returncode == 0


def load_config() -> dict:
    """Load configuration from ~/.agentwire/config.yaml."""
    config_path = CONFIG_DIR / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


# === Wave 2: Remote Infrastructure Helpers ===


def _get_machine_config(machine_id: str) -> dict | None:
    """Load machine config from machines.json.

    Returns:
        Machine dict with id, host, user, projects_dir, etc.
        None if machine not found.
    """
    machines_file = CONFIG_DIR / "machines.json"
    if not machines_file.exists():
        return None

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    machines = machines_data.get("machines", [])
    for m in machines:
        if m.get("id") == machine_id:
            return m

    return None


def _parse_session_target(name: str) -> tuple[str, str | None]:
    """Parse 'session@machine' into (session, machine_id).

    Examples:
        "myapp" -> ("myapp", None)
        "myapp@gpu-server" -> ("myapp", "gpu-server")
        "myapp/feature@gpu-server" -> ("myapp/feature", "gpu-server")
    """
    if "@" in name:
        session, machine = name.rsplit("@", 1)
        return session, machine
    return name, None


def _run_remote(machine_id: str, command: str) -> subprocess.CompletedProcess:
    """Run command on remote machine via SSH.

    Args:
        machine_id: Machine ID from machines.json
        command: Shell command to run

    Returns:
        subprocess.CompletedProcess with stdout, stderr, returncode
    """
    machine = _get_machine_config(machine_id)
    if machine is None:
        # Return a failed result
        result = subprocess.CompletedProcess(
            args=["ssh", machine_id, command],
            returncode=1,
            stdout="",
            stderr=f"Machine '{machine_id}' not found in machines.json",
        )
        return result

    host = machine.get("host", machine_id)
    user = machine.get("user")

    # Build SSH target
    if user:
        ssh_target = f"{user}@{host}"
    else:
        ssh_target = host

    return subprocess.run(
        ["ssh", ssh_target, command],
        capture_output=True,
        text=True,
    )


def _get_all_machines() -> list[dict]:
    """Get list of all registered machines from machines.json."""
    machines_file = CONFIG_DIR / "machines.json"
    if not machines_file.exists():
        return []

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
            return machines_data.get("machines", [])
    except (json.JSONDecodeError, IOError):
        return []


def _output_json(data: dict) -> None:
    """Output JSON to stdout."""
    print(json.dumps(data, indent=2))


def _output_result(success: bool, json_mode: bool, message: str = "", **kwargs) -> int:
    """Output result in text or JSON mode.

    Returns:
        0 if success, 1 otherwise
    """
    if json_mode:
        result = {"success": success, **kwargs}
        if not success and "error" not in result:
            result["error"] = message
        _output_json(result)
    else:
        if message:
            if success:
                print(message)
            else:
                print(message, file=sys.stderr)
    return 0 if success else 1


# === Portal Commands ===

def cmd_portal_start(args) -> int:
    """Start the AgentWire portal web server in tmux."""
    session_name = "agentwire-portal"

    if tmux_session_exists(session_name):
        print(f"Portal already running in tmux session '{session_name}'")
        print(f"Attaching... (Ctrl+B D to detach)")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    # Build the server command
    # --dev runs from source with uv run (picks up code changes immediately)
    if getattr(args, 'dev', False):
        cmd_parts = ["uv", "run", "python", "-m", "agentwire", "portal", "serve"]
    else:
        cmd_parts = ["agentwire", "portal", "serve"]

    if args.port:
        cmd_parts.extend(["--port", str(args.port)])
    if args.host:
        cmd_parts.extend(["--host", args.host])
    if args.no_tts:
        cmd_parts.append("--no-tts")
    if args.no_stt:
        cmd_parts.append("--no-stt")
    if args.config:
        cmd_parts.extend(["--config", str(args.config)])

    server_cmd = " ".join(cmd_parts)

    # Create tmux session and start server
    mode = "dev mode (from source)" if getattr(args, 'dev', False) else "installed"
    print(f"Starting AgentWire portal ({mode}) in tmux session '{session_name}'...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, server_cmd, "Enter",
    ])

    print(f"Portal started. Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


def cmd_portal_serve(args) -> int:
    """Run the web server directly (foreground)."""
    from .server import main as server_main

    server_main(
        config_path=str(args.config) if args.config else None,
        port=args.port,
        host=args.host,
        no_tts=args.no_tts,
        no_stt=args.no_stt,
    )
    return 0


def cmd_portal_stop(args) -> int:
    """Stop the AgentWire portal."""
    session_name = "agentwire-portal"

    if not tmux_session_exists(session_name):
        print("Portal is not running.")
        return 1

    subprocess.run(["tmux", "kill-session", "-t", session_name])
    print("Portal stopped.")
    return 0


def cmd_portal_status(args) -> int:
    """Check portal status."""
    session_name = "agentwire-portal"

    if tmux_session_exists(session_name):
        print(f"Portal is running in tmux session '{session_name}'")
        print(f"  Attach: tmux attach -t {session_name}")
        return 0
    else:
        print("Portal is not running.")
        print("  Start:  agentwire portal start")
        return 1


# === TTS Commands ===

def cmd_tts_start(args) -> int:
    """Start the Chatterbox TTS server in tmux."""
    session_name = "agentwire-tts"

    if tmux_session_exists(session_name):
        print(f"TTS server already running in tmux session '{session_name}'")
        print(f"Attaching... (Ctrl+B D to detach)")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    # Get TTS config
    config = load_config()
    tts_config = config.get("tts", {})
    port = args.port or tts_config.get("port", 8100)
    host = args.host or tts_config.get("host", "0.0.0.0")

    # Build the serve command
    tts_cmd = f"agentwire tts serve --host {host} --port {port}"

    print(f"Starting TTS server on {host}:{port}...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, tts_cmd, "Enter",
    ])

    print(f"TTS server started. Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


def cmd_tts_serve(args) -> int:
    """Run the TTS server directly (foreground)."""
    import uvicorn

    config = load_config()
    tts_config = config.get("tts", {})
    port = args.port or tts_config.get("port", 8100)
    host = args.host or tts_config.get("host", "0.0.0.0")

    print(f"Starting TTS server on {host}:{port}...")
    uvicorn.run(
        "agentwire.tts_server:app",
        host=host,
        port=port,
        log_level="info",
    )
    return 0


def cmd_tts_stop(args) -> int:
    """Stop the TTS server."""
    session_name = "agentwire-tts"

    if not tmux_session_exists(session_name):
        print("TTS server is not running.")
        return 1

    subprocess.run(["tmux", "kill-session", "-t", session_name])
    print("TTS server stopped.")
    return 0


def cmd_tts_status(args) -> int:
    """Check TTS server status."""
    session_name = "agentwire-tts"

    if tmux_session_exists(session_name):
        print(f"TTS server is running in tmux session '{session_name}'")
        print(f"  Attach: tmux attach -t {session_name}")

        # Try to check if it's responding
        config = load_config()
        tts_url = config.get("tts", {}).get("url", "http://localhost:8100")
        try:
            import urllib.request
            req = urllib.request.urlopen(f"{tts_url}/voices", timeout=2)
            voices = json.loads(req.read().decode())
            print(f"  Voices: {', '.join(voices) if isinstance(voices, list) else 'available'}")
        except Exception:
            print("  Status: starting or not responding yet")

        return 0
    else:
        print("TTS server is not running.")
        print("  Start:  agentwire tts start")
        return 1


# === Say Command ===

def cmd_say(args) -> int:
    """Generate TTS audio and play it."""
    text = " ".join(args.text) if args.text else ""

    if not text:
        print("Usage: agentwire say <text>", file=sys.stderr)
        return 1

    config = load_config()
    tts_config = config.get("tts", {})
    tts_url = tts_config.get("url", "http://localhost:8100")
    voice = args.voice or tts_config.get("default_voice", "default")
    exaggeration = args.exaggeration or tts_config.get("exaggeration", 0.5)
    cfg_weight = args.cfg or tts_config.get("cfg_weight", 0.5)

    # Check if this is a remote session (room specified)
    if args.room:
        # Use remote-say: POST to portal
        portal_url = config.get("portal", {}).get("url", "https://localhost:8765")
        return _remote_say(text, args.room, portal_url)

    # Local TTS: generate and play
    return _local_say(text, voice, exaggeration, cfg_weight, tts_url)


def _local_say(text: str, voice: str, exaggeration: float, cfg_weight: float, tts_url: str) -> int:
    """Generate TTS locally and play via system audio."""
    import urllib.request
    import tempfile

    try:
        # Request audio from chatterbox
        data = json.dumps({
            "text": text,
            "voice": voice,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
        }).encode()

        req = urllib.request.Request(
            f"{tts_url}/tts",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            audio_data = response.read()

        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        # Play audio (cross-platform)
        if sys.platform == "darwin":
            subprocess.run(["afplay", temp_path], check=True)
        elif sys.platform == "linux":
            # Try various players
            for player in ["aplay", "paplay", "play"]:
                try:
                    subprocess.run([player, temp_path], check=True)
                    break
                except FileNotFoundError:
                    continue
        else:
            print(f"Audio saved to: {temp_path}")

        # Clean up
        Path(temp_path).unlink(missing_ok=True)
        return 0

    except urllib.error.URLError as e:
        print(f"TTS server not reachable: {e}", file=sys.stderr)
        print("Start it with: agentwire tts start", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"TTS failed: {e}", file=sys.stderr)
        return 1


def _remote_say(text: str, room: str, portal_url: str) -> int:
    """Send TTS to a room via the portal (for remote sessions)."""
    import urllib.request
    import ssl

    try:
        # Create SSL context that doesn't verify (self-signed certs)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        data = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            f"{portal_url}/api/say/{room}",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            result = json.loads(response.read().decode())
            if result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)
                return 1

        return 0

    except Exception as e:
        print(f"Failed to send to portal: {e}", file=sys.stderr)
        return 1


# === Session Commands ===

def cmd_send(args) -> int:
    """Send a prompt to a tmux session (adds Enter automatically).

    Supports remote sessions with session@machine format.
    """
    session_full = args.session
    prompt = " ".join(args.prompt) if args.prompt else ""

    if not session_full:
        print("Usage: agentwire send -s <session> <prompt>", file=sys.stderr)
        return 1

    if not prompt:
        print("Usage: agentwire send -s <session> <prompt>", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux commands
        machine = _get_machine_config(machine_id)
        if machine is None:
            print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        # Build remote command
        quoted_session = shlex.quote(session)
        quoted_prompt = shlex.quote(prompt)

        # Send text, sleep, send Enter
        cmd = f"tmux send-keys -t {quoted_session} {quoted_prompt} && sleep 0.3 && tmux send-keys -t {quoted_session} Enter"

        # For multi-line text, add another Enter
        if "\n" in prompt or len(prompt) > 200:
            cmd += f" && sleep 0.5 && tmux send-keys -t {quoted_session} Enter"

        result = _run_remote(machine_id, cmd)
        if result.returncode != 0:
            print(f"Failed to send to {session_full}: {result.stderr}", file=sys.stderr)
            return 1

        print(f"Sent to {session_full}")
        return 0

    # Local: existing logic
    # Check if session exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    # Send the prompt via tmux send-keys (text first, then Enter after delay)
    subprocess.run(
        ["tmux", "send-keys", "-t", session, prompt],
        check=True
    )

    # Wait for text to be fully entered before pressing Enter
    time.sleep(0.3)

    subprocess.run(
        ["tmux", "send-keys", "-t", session, "Enter"],
        check=True
    )

    # For multi-line text, Claude Code shows "[Pasted text...]" and waits for Enter
    # Send another Enter after a short delay to confirm the paste
    if "\n" in prompt or len(prompt) > 200:
        time.sleep(0.5)
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"],
            check=True
        )

    print(f"Sent to {session}")
    return 0


def cmd_list(args) -> int:
    """List all tmux sessions from local and all registered machines."""
    json_mode = getattr(args, 'json', False)
    local_only = getattr(args, 'local', False)

    all_sessions = []

    # Get local sessions
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}:#{session_windows}:#{pane_current_path}"],
        capture_output=True,
        text=True
    )

    local_sessions = []
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    session_info = {
                        "name": parts[0],
                        "windows": int(parts[1]) if parts[1].isdigit() else 1,
                        "path": parts[2] if len(parts) > 2 else "",
                        "machine": None,
                    }
                    local_sessions.append(session_info)
                    all_sessions.append(session_info)

    # Get remote sessions from all registered machines
    remote_by_machine = {}
    if not local_only:
        machines = _get_all_machines()
        for machine in machines:
            machine_id = machine.get("id")
            if not machine_id:
                continue

            cmd = "tmux list-sessions -F '#{session_name}:#{session_windows}:#{pane_current_path}' 2>/dev/null || echo ''"
            result = _run_remote(machine_id, cmd)

            machine_sessions = []
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            session_info = {
                                "name": f"{parts[0]}@{machine_id}",
                                "windows": int(parts[1]) if parts[1].isdigit() else 1,
                                "path": parts[2] if len(parts) > 2 else "",
                                "machine": machine_id,
                            }
                            machine_sessions.append(session_info)
                            all_sessions.append(session_info)

            remote_by_machine[machine_id] = machine_sessions

    # Output
    if json_mode:
        _output_json({"success": True, "sessions": all_sessions})
        return 0

    # Text output - grouped by machine
    if not local_sessions and not any(remote_by_machine.values()):
        print("No sessions running")
        return 0

    # Local sessions
    if local_sessions:
        print("LOCAL:")
        for s in local_sessions:
            print(f"  {s['name']}: {s['windows']} window(s) ({s['path']})")
        print()

    # Remote sessions
    for machine_id, sessions in remote_by_machine.items():
        print(f"{machine_id}:")
        if sessions:
            for s in sessions:
                # Remove @machine suffix for display within machine group
                display_name = s['name'].rsplit('@', 1)[0] if '@' in s['name'] else s['name']
                print(f"  {display_name}: {s['windows']} window(s) ({s['path']})")
        else:
            print("  (no sessions)")
        print()

    return 0


def cmd_new(args) -> int:
    """Create a new Claude Code session in tmux.

    Supports:
    - "project" -> simple session in ~/projects/project/
    - "project/branch" -> worktree session in ~/projects/project-worktrees/branch/
    - "project@machine" -> remote session
    - "project/branch@machine" -> remote worktree session
    """
    name = args.session
    path = args.path
    json_mode = getattr(args, 'json', False)

    if not name:
        return _output_result(False, json_mode, "Usage: agentwire new -s <name> [-p path] [-f]")

    # Parse session name: project, branch, machine
    project, branch, machine_id = parse_session_name(name)

    # Build the tmux session name (convert dots/slashes to underscores)
    if branch:
        session_name = f"{project}_{branch}".replace(".", "_").replace("/", "_")
    else:
        session_name = project.replace(".", "_")

    # Load config
    config = load_config()
    projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
    worktrees_config = config.get("projects", {}).get("worktrees", {})
    worktrees_enabled = worktrees_config.get("enabled", True)
    worktree_suffix = worktrees_config.get("suffix", "-worktrees")
    auto_create_branch = worktrees_config.get("auto_create_branch", True)

    # Handle remote session
    if machine_id:
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_projects_dir = machine.get("projects_dir", "~/projects")

        # Build remote path
        if path:
            remote_path = path
        elif branch:
            remote_path = f"{remote_projects_dir}/{project}{worktree_suffix}/{branch}"
        else:
            remote_path = f"{remote_projects_dir}/{project}"

        # If branch specified, create worktree on remote
        if branch:
            # Create worktree on remote
            project_path = f"{remote_projects_dir}/{project}"
            worktree_path = remote_path

            # Check if worktree already exists
            check_cmd = f"test -d {shlex.quote(worktree_path)}"
            result = _run_remote(machine_id, check_cmd)

            if result.returncode != 0:
                # Create worktree
                # First check if branch exists
                branch_check = f"cd {shlex.quote(project_path)} && git rev-parse --verify refs/heads/{shlex.quote(branch)} 2>/dev/null"
                result = _run_remote(machine_id, branch_check)

                if result.returncode == 0:
                    # Branch exists, create worktree
                    create_cmd = f"cd {shlex.quote(project_path)} && mkdir -p $(dirname {shlex.quote(worktree_path)}) && git worktree add {shlex.quote(worktree_path)} {shlex.quote(branch)}"
                elif auto_create_branch:
                    # Create branch with worktree
                    create_cmd = f"cd {shlex.quote(project_path)} && mkdir -p $(dirname {shlex.quote(worktree_path)}) && git worktree add -b {shlex.quote(branch)} {shlex.quote(worktree_path)}"
                else:
                    return _output_result(False, json_mode, f"Branch '{branch}' does not exist and auto_create_branch is disabled")

                result = _run_remote(machine_id, create_cmd)
                if result.returncode != 0:
                    return _output_result(False, json_mode, f"Failed to create remote worktree: {result.stderr}")

        # Check if remote session already exists
        check_cmd = f"tmux has-session -t ={shlex.quote(session_name)} 2>/dev/null"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode == 0:
            if args.force:
                # Kill existing session
                kill_cmd = f"tmux send-keys -t {shlex.quote(session_name)} /exit Enter && sleep 2 && tmux kill-session -t {shlex.quote(session_name)} 2>/dev/null"
                _run_remote(machine_id, kill_cmd)
            else:
                return _output_result(False, json_mode, f"Session '{session_name}' already exists on {machine_id}. Use -f to replace.")

        # Create remote tmux session
        # Restricted mode implies no bypass (needs permission hook for auto-deny logic)
        use_no_bypass = getattr(args, 'no_bypass', False) or getattr(args, 'restricted', False)
        bypass_flag = "" if use_no_bypass else " --dangerously-skip-permissions"
        create_cmd = (
            f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(remote_path)} && "
            f"tmux send-keys -t {shlex.quote(session_name)} 'export AGENTWIRE_ROOM={shlex.quote(session_name)}' Enter && "
            f"sleep 0.1 && "
            f"tmux send-keys -t {shlex.quote(session_name)} 'claude{bypass_flag}' Enter"
        )

        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create remote session: {result.stderr}")

        # Update local rooms.json with remote session info
        rooms_file = Path.home() / ".agentwire" / "rooms.json"
        rooms_file.parent.mkdir(parents=True, exist_ok=True)

        configs = {}
        if rooms_file.exists():
            try:
                with open(rooms_file) as f:
                    configs = json.load(f)
            except Exception:
                pass

        room_key = f"{session_name}@{machine_id}"
        restricted = getattr(args, 'restricted', False)
        bypass_permissions = not use_no_bypass
        configs[room_key] = {"bypass_permissions": bypass_permissions, "restricted": restricted}

        with open(rooms_file, "w") as f:
            json.dump(configs, f, indent=2)

        if json_mode:
            _output_json({
                "success": True,
                "session": f"{session_name}@{machine_id}",
                "path": remote_path,
                "branch": branch,
                "machine": machine_id,
            })
        else:
            print(f"Created session '{session_name}' on {machine_id} in {remote_path}")
            print(f"Attach via portal or: ssh {machine.get('host', machine_id)} -t tmux attach -t {session_name}")

        return 0

    # Local session
    # Resolve path
    if path and branch and worktrees_enabled:
        # Path + branch: use provided path as main repo, create worktree from it
        project_path = Path(path).expanduser().resolve()
        session_path = project_path.parent / f"{project_path.name}{worktree_suffix}" / branch

        # Ensure worktree exists
        if not session_path.exists():
            if not project_path.exists():
                return _output_result(False, json_mode, f"Project path does not exist: {project_path}")

            success = ensure_worktree(
                project_path,
                branch,
                session_path,
                auto_create_branch=auto_create_branch,
            )
            if not success:
                return _output_result(False, json_mode, f"Failed to create worktree for branch '{branch}' in {project_path}")
    elif path:
        session_path = Path(path).expanduser().resolve()
    elif branch and worktrees_enabled:
        # Worktree session: ~/projects/project-worktrees/branch/
        project_path = projects_dir / project
        session_path = projects_dir / f"{project}{worktree_suffix}" / branch

        # Ensure worktree exists
        if not session_path.exists():
            if not project_path.exists():
                return _output_result(False, json_mode, f"Project path does not exist: {project_path}")

            success = ensure_worktree(
                project_path,
                branch,
                session_path,
                auto_create_branch=auto_create_branch,
            )
            if not success:
                return _output_result(False, json_mode, f"Failed to create worktree for branch '{branch}' in {project_path}")
    else:
        # Simple session: ~/projects/project/
        session_path = projects_dir / project

    if not session_path.exists():
        return _output_result(False, json_mode, f"Path does not exist: {session_path}")

    # Check if session already exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={session_name}"],
        capture_output=True
    )
    if result.returncode == 0:
        if args.force:
            # Kill existing session
            subprocess.run(["tmux", "send-keys", "-t", session_name, "/exit", "Enter"])
            time.sleep(2)
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        else:
            return _output_result(False, json_mode, f"Session '{session_name}' already exists. Use -f to replace.")

    # Create new tmux session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", str(session_path)],
        check=True
    )

    # Set AGENTWIRE_ROOM env var (used by permission hook)
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, f"export AGENTWIRE_ROOM={session_name}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    # Start Claude (with or without skip-permissions flag)
    # Restricted mode implies no bypass (needs permission hook for auto-deny logic)
    use_no_bypass = getattr(args, 'no_bypass', False) or getattr(args, 'restricted', False)
    if use_no_bypass:
        claude_cmd = "claude"
    else:
        claude_cmd = "claude --dangerously-skip-permissions"

    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, claude_cmd, "Enter"],
        check=True
    )

    # Save room config with bypass_permissions and restricted flags
    rooms_file = Path.home() / ".agentwire" / "rooms.json"
    rooms_file.parent.mkdir(parents=True, exist_ok=True)

    configs = {}
    if rooms_file.exists():
        try:
            with open(rooms_file) as f:
                configs = json.load(f)
        except Exception:
            pass

    restricted = getattr(args, 'restricted', False)
    bypass_permissions = not use_no_bypass
    configs[session_name] = {"bypass_permissions": bypass_permissions, "restricted": restricted}

    with open(rooms_file, "w") as f:
        json.dump(configs, f, indent=2)

    if json_mode:
        _output_json({
            "success": True,
            "session": session_name,
            "path": str(session_path),
            "branch": branch,
            "machine": None,
        })
    else:
        print(f"Created session '{session_name}' in {session_path}")
        print(f"Attach with: tmux attach -t {session_name}")

    return 0


def cmd_output(args) -> int:
    """Read output from a tmux session.

    Supports remote sessions with session@machine format.
    """
    session_full = args.session
    lines = args.lines or 50

    if not session_full:
        print("Usage: agentwire output -s <session> [-n lines]", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux capture-pane
        machine = _get_machine_config(machine_id)
        if machine is None:
            print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        cmd = f"tmux capture-pane -t {shlex.quote(session)} -p -S -{lines}"
        result = _run_remote(machine_id, cmd)

        if result.returncode != 0:
            print(f"Session '{session}' not found on {machine_id}", file=sys.stderr)
            return 1

        print(result.stdout)
        return 0

    # Local: existing logic
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    return 0


def cmd_kill(args) -> int:
    """Kill a tmux session (with clean Claude exit).

    Supports remote sessions with session@machine format.
    """
    session_full = args.session

    if not session_full:
        print("Usage: agentwire kill -s <session>", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux commands
        machine = _get_machine_config(machine_id)
        if machine is None:
            print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        # Check if session exists
        check_cmd = f"tmux has-session -t {shlex.quote(session)} 2>/dev/null"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode != 0:
            print(f"Session '{session}' not found on {machine_id}", file=sys.stderr)
            return 1

        # Send /exit to Claude first for clean shutdown
        exit_cmd = f"tmux send-keys -t {shlex.quote(session)} /exit Enter"
        _run_remote(machine_id, exit_cmd)
        print(f"Sent /exit to {session_full}, waiting 3s...")
        time.sleep(3)

        # Kill the session
        kill_cmd = f"tmux kill-session -t {shlex.quote(session)}"
        _run_remote(machine_id, kill_cmd)
        print(f"Killed session '{session_full}'")

        # Clean up rooms.json
        rooms_file = Path.home() / ".agentwire" / "rooms.json"
        if rooms_file.exists():
            try:
                with open(rooms_file) as f:
                    configs = json.load(f)

                room_key = f"{session}@{machine_id}"
                if room_key in configs:
                    del configs[room_key]
                    with open(rooms_file, "w") as f:
                        json.dump(configs, f, indent=2)
            except Exception:
                pass

        return 0

    # Local: existing logic
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    # Send /exit to Claude first for clean shutdown
    subprocess.run(["tmux", "send-keys", "-t", session, "/exit", "Enter"])
    print(f"Sent /exit to {session}, waiting 3s...")
    time.sleep(3)

    # Kill the session
    subprocess.run(["tmux", "kill-session", "-t", session])
    print(f"Killed session '{session}'")

    # Clean up rooms.json
    rooms_file = Path.home() / ".agentwire" / "rooms.json"
    if rooms_file.exists():
        try:
            with open(rooms_file) as f:
                configs = json.load(f)

            if session in configs:
                del configs[session]
                with open(rooms_file, "w") as f:
                    json.dump(configs, f, indent=2)
        except Exception:
            pass

    return 0


def cmd_send_keys(args) -> int:
    """Send raw keys to a tmux session (no automatic Enter).

    Each argument is sent as a separate key group with a brief pause between.
    Useful for sending special keys like Enter, Escape, C-c, etc.

    Supports remote sessions with session@machine format.
    """
    session_full = args.session
    keys = args.keys if args.keys else []

    if not session_full:
        print("Usage: agentwire send-keys -s <session> <keys>...", file=sys.stderr)
        return 1

    if not keys:
        print("Usage: agentwire send-keys -s <session> <keys>...", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  agentwire send-keys -s mysession Enter", file=sys.stderr)
        print("  agentwire send-keys -s mysession C-c", file=sys.stderr)
        print("  agentwire send-keys -s mysession Escape", file=sys.stderr)
        print("  agentwire send-keys -s mysession 'hello world' Enter", file=sys.stderr)
        return 1

    # Parse session@machine format
    session, machine_id = _parse_session_target(session_full)

    if machine_id:
        # Remote: SSH and run tmux commands
        machine = _get_machine_config(machine_id)
        if machine is None:
            print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
            return 1

        # Build remote command with pauses between keys
        quoted_session = shlex.quote(session)
        cmd_parts = []
        for i, key in enumerate(keys):
            cmd_parts.append(f"tmux send-keys -t {quoted_session} {shlex.quote(key)}")
            if i < len(keys) - 1:
                cmd_parts.append("sleep 0.1")

        cmd = " && ".join(cmd_parts)

        result = _run_remote(machine_id, cmd)
        if result.returncode != 0:
            print(f"Failed to send keys to {session_full}: {result.stderr}", file=sys.stderr)
            return 1

        print(f"Sent keys to {session_full}")
        return 0

    # Local: existing logic
    # Check if session exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    # Send each key group with a pause between
    for i, key in enumerate(keys):
        subprocess.run(
            ["tmux", "send-keys", "-t", session, key],
            check=True
        )
        # Brief pause between key groups (not after last one)
        if i < len(keys) - 1:
            time.sleep(0.1)

    print(f"Sent keys to {session}")
    return 0


def cmd_session_new(args) -> int:
    """Create a new Claude Code session in tmux."""
    name = args.name
    path = args.path

    # Convert dots to underscores for tmux session name
    session_name = name.replace(".", "_")

    # Resolve path
    if path:
        session_path = Path(path).expanduser().resolve()
    else:
        # Default to ~/projects/<name> (using original name with dots)
        config = load_config()
        projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
        session_path = projects_dir / name

    if not session_path.exists():
        print(f"Path does not exist: {session_path}", file=sys.stderr)
        return 1

    # Check if session already exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True
    )
    if result.returncode == 0:
        if args.force:
            # Kill existing session
            subprocess.run(["tmux", "send-keys", "-t", session_name, "/exit", "Enter"])
            time.sleep(2)
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        else:
            print(f"Session '{session_name}' already exists. Use --force to replace.", file=sys.stderr)
            return 1

    # Create new tmux session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", str(session_path)],
        check=True
    )

    # Start Claude with skip-permissions flag
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "claude --dangerously-skip-permissions", "Enter"],
        check=True
    )

    print(f"Created session '{session_name}' in {session_path}")
    print(f"Attach with: tmux attach -t {session_name}")
    return 0


def cmd_session_list(args) -> int:
    """List all tmux sessions."""
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}: #{session_windows} windows (#{session_path})"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("No sessions running")
        return 0

    print(result.stdout.strip())
    return 0


def cmd_session_output(args) -> int:
    """Read output from a tmux session."""
    session = args.session
    lines = args.lines or 50

    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    return 0


def cmd_session_kill(args) -> int:
    """Kill a tmux session (with clean Claude exit)."""
    session = args.session

    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Session '{session}' not found", file=sys.stderr)
        return 1

    # Send /exit to Claude first for clean shutdown
    subprocess.run(["tmux", "send-keys", "-t", session, "/exit", "Enter"])
    print(f"Sent /exit to {session}, waiting 3s...")
    time.sleep(3)

    # Kill the session
    subprocess.run(["tmux", "kill-session", "-t", session])
    print(f"Killed session '{session}'")
    return 0


# === Wave 5: Recreate and Fork Commands ===


def cmd_recreate(args) -> int:
    """Destroy and recreate a session with fresh worktree.

    Steps:
    1. Kill existing session (local or remote)
    2. Remove worktree
    3. Pull latest on main repo
    4. Create new worktree with timestamp branch
    5. Create new session

    Supports remote sessions with session@machine format.
    """
    session_full = args.session
    json_mode = getattr(args, 'json', False)

    if not session_full:
        return _output_result(False, json_mode, "Usage: agentwire recreate -s <session>")

    # Parse session name
    project, branch, machine_id = parse_session_name(session_full)

    # Load config
    config = load_config()
    projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
    worktrees_config = config.get("projects", {}).get("worktrees", {})
    worktree_suffix = worktrees_config.get("suffix", "-worktrees")

    # Build session name for tmux
    if branch:
        session_name = f"{project}_{branch}".replace(".", "_").replace("/", "_")
    else:
        session_name = project.replace(".", "_")

    if machine_id:
        # Remote recreate
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_projects_dir = machine.get("projects_dir", "~/projects")

        # Step 1: Kill existing session
        kill_cmd = f"tmux send-keys -t {shlex.quote(session_name)} /exit Enter 2>/dev/null; sleep 2; tmux kill-session -t {shlex.quote(session_name)} 2>/dev/null"
        _run_remote(machine_id, kill_cmd)

        # Determine paths
        project_path = f"{remote_projects_dir}/{project}"
        if branch:
            worktree_path = f"{remote_projects_dir}/{project}{worktree_suffix}/{branch}"
        else:
            worktree_path = project_path

        # Step 2: Remove worktree (if branch session)
        if branch:
            remove_cmd = f"cd {shlex.quote(project_path)} && git worktree remove {shlex.quote(worktree_path)} --force 2>/dev/null; rm -rf {shlex.quote(worktree_path)}"
            _run_remote(machine_id, remove_cmd)

        # Step 3: Pull latest on main repo
        pull_cmd = f"cd {shlex.quote(project_path)} && git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true"
        _run_remote(machine_id, pull_cmd)

        # Step 4: Create new worktree with timestamp branch
        if branch:
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            new_branch = f"{branch}-{timestamp}"

            create_wt_cmd = f"cd {shlex.quote(project_path)} && mkdir -p $(dirname {shlex.quote(worktree_path)}) && git worktree add -b {shlex.quote(new_branch)} {shlex.quote(worktree_path)}"
            result = _run_remote(machine_id, create_wt_cmd)
            if result.returncode != 0:
                return _output_result(False, json_mode, f"Failed to create worktree: {result.stderr}")

        # Step 5: Create new session
        bypass_flag = "" if getattr(args, 'no_bypass', False) else " --dangerously-skip-permissions"
        session_path = worktree_path if branch else project_path

        create_cmd = (
            f"tmux new-session -d -s {shlex.quote(session_name)} -c {shlex.quote(session_path)} && "
            f"tmux send-keys -t {shlex.quote(session_name)} 'export AGENTWIRE_ROOM={shlex.quote(session_name)}' Enter && "
            f"sleep 0.1 && "
            f"tmux send-keys -t {shlex.quote(session_name)} 'claude{bypass_flag}' Enter"
        )

        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create session: {result.stderr}")

        if json_mode:
            _output_json({
                "success": True,
                "session": f"{session_name}@{machine_id}",
                "path": session_path,
                "branch": new_branch if branch else None,
                "machine": machine_id,
            })
        else:
            print(f"Recreated session '{session_name}' on {machine_id} in {session_path}")

        return 0

    # Local recreate
    # Step 1: Kill existing session
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={session_name}"],
        capture_output=True
    )
    if result.returncode == 0:
        subprocess.run(["tmux", "send-keys", "-t", session_name, "/exit", "Enter"])
        time.sleep(2)
        subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

    # Determine paths
    project_path = projects_dir / project
    if branch:
        worktree_path = projects_dir / f"{project}{worktree_suffix}" / branch
    else:
        worktree_path = project_path

    # Step 2: Remove worktree (if branch session)
    if branch and worktree_path.exists():
        remove_worktree(project_path, worktree_path)
        # Force remove if git worktree remove failed
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    # Step 3: Pull latest on main repo
    if project_path.exists():
        subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=project_path,
            capture_output=True
        )

    # Step 4: Create new worktree with timestamp branch
    if branch:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        new_branch = f"{branch}-{timestamp}"

        success = ensure_worktree(
            project_path,
            new_branch,
            worktree_path,
            auto_create_branch=True,
        )
        if not success:
            return _output_result(False, json_mode, f"Failed to create worktree for branch '{new_branch}'")

    session_path = worktree_path if branch else project_path

    if not session_path.exists():
        return _output_result(False, json_mode, f"Path does not exist: {session_path}")

    # Step 5: Create new session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", str(session_path)],
        check=True
    )

    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, f"export AGENTWIRE_ROOM={session_name}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    if getattr(args, 'no_bypass', False):
        claude_cmd = "claude"
    else:
        claude_cmd = "claude --dangerously-skip-permissions"

    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, claude_cmd, "Enter"],
        check=True
    )

    # Update rooms.json
    rooms_file = Path.home() / ".agentwire" / "rooms.json"
    rooms_file.parent.mkdir(parents=True, exist_ok=True)

    configs = {}
    if rooms_file.exists():
        try:
            with open(rooms_file) as f:
                configs = json.load(f)
        except Exception:
            pass

    bypass_permissions = not getattr(args, 'no_bypass', False)
    configs[session_name] = {"bypass_permissions": bypass_permissions}

    with open(rooms_file, "w") as f:
        json.dump(configs, f, indent=2)

    if json_mode:
        _output_json({
            "success": True,
            "session": session_name,
            "path": str(session_path),
            "branch": new_branch if branch else None,
            "machine": None,
        })
    else:
        print(f"Recreated session '{session_name}' in {session_path}")
        print(f"Attach with: tmux attach -t {session_name}")

    return 0


def cmd_fork(args) -> int:
    """Fork a session into a new worktree with copied Claude context.

    Creates a new worktree from current branch state and optionally
    copies Claude session file for conversation continuity.

    Supports remote sessions with session@machine format.
    """
    source_full = args.source
    target_full = args.target
    json_mode = getattr(args, 'json', False)

    if not source_full or not target_full:
        return _output_result(False, json_mode, "Usage: agentwire fork -s <source> -t <target>")

    # Parse session names
    source_project, source_branch, source_machine = parse_session_name(source_full)
    target_project, target_branch, target_machine = parse_session_name(target_full)

    # Validate: source and target should be same project
    if source_project != target_project:
        return _output_result(False, json_mode, f"Source and target must be same project (got {source_project} vs {target_project})")

    # Validate: target must have a branch
    if not target_branch:
        return _output_result(False, json_mode, "Target must include a branch name (e.g., project/new-branch)")

    # Machines must match
    if source_machine != target_machine:
        return _output_result(False, json_mode, f"Source and target must be on same machine (got {source_machine} vs {target_machine})")

    machine_id = source_machine

    # Load config
    config = load_config()
    projects_dir = Path(config.get("projects", {}).get("dir", "~/projects")).expanduser()
    worktrees_config = config.get("projects", {}).get("worktrees", {})
    worktree_suffix = worktrees_config.get("suffix", "-worktrees")

    # Build session names
    if source_branch:
        source_session = f"{source_project}_{source_branch}".replace(".", "_").replace("/", "_")
    else:
        source_session = source_project.replace(".", "_")

    target_session = f"{target_project}_{target_branch}".replace(".", "_").replace("/", "_")

    if machine_id:
        # Remote fork
        machine = _get_machine_config(machine_id)
        if machine is None:
            return _output_result(False, json_mode, f"Machine '{machine_id}' not found in machines.json")

        remote_projects_dir = machine.get("projects_dir", "~/projects")

        # Build paths
        project_path = f"{remote_projects_dir}/{source_project}"
        if source_branch:
            source_path = f"{remote_projects_dir}/{source_project}{worktree_suffix}/{source_branch}"
        else:
            source_path = project_path
        target_path = f"{remote_projects_dir}/{target_project}{worktree_suffix}/{target_branch}"

        # Check if target already exists
        check_cmd = f"test -d {shlex.quote(target_path)}"
        result = _run_remote(machine_id, check_cmd)
        if result.returncode == 0:
            return _output_result(False, json_mode, f"Target worktree already exists: {target_path}")

        # Create new worktree from source
        create_cmd = f"cd {shlex.quote(source_path)} && mkdir -p $(dirname {shlex.quote(target_path)}) && git worktree add -b {shlex.quote(target_branch)} {shlex.quote(target_path)}"
        result = _run_remote(machine_id, create_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create worktree: {result.stderr}")

        # Create new session
        bypass_flag = "" if getattr(args, 'no_bypass', False) else " --dangerously-skip-permissions"
        create_session_cmd = (
            f"tmux new-session -d -s {shlex.quote(target_session)} -c {shlex.quote(target_path)} && "
            f"tmux send-keys -t {shlex.quote(target_session)} 'export AGENTWIRE_ROOM={shlex.quote(target_session)}' Enter && "
            f"sleep 0.1 && "
            f"tmux send-keys -t {shlex.quote(target_session)} 'claude{bypass_flag}' Enter"
        )

        result = _run_remote(machine_id, create_session_cmd)
        if result.returncode != 0:
            return _output_result(False, json_mode, f"Failed to create session: {result.stderr}")

        # Update local rooms.json
        rooms_file = Path.home() / ".agentwire" / "rooms.json"
        rooms_file.parent.mkdir(parents=True, exist_ok=True)

        configs = {}
        if rooms_file.exists():
            try:
                with open(rooms_file) as f:
                    configs = json.load(f)
            except Exception:
                pass

        room_key = f"{target_session}@{machine_id}"
        bypass_permissions = not getattr(args, 'no_bypass', False)
        configs[room_key] = {"bypass_permissions": bypass_permissions}

        with open(rooms_file, "w") as f:
            json.dump(configs, f, indent=2)

        if json_mode:
            _output_json({
                "success": True,
                "session": f"{target_session}@{machine_id}",
                "path": target_path,
                "branch": target_branch,
                "machine": machine_id,
                "forked_from": source_full,
            })
        else:
            print(f"Forked '{source_full}' to '{target_session}' on {machine_id}")
            print(f"  Path: {target_path}")

        return 0

    # Local fork
    # Build paths
    project_path = projects_dir / source_project
    if source_branch:
        source_path = projects_dir / f"{source_project}{worktree_suffix}" / source_branch
    else:
        source_path = project_path
    target_path = projects_dir / f"{target_project}{worktree_suffix}" / target_branch

    # Check if target already exists
    if target_path.exists():
        return _output_result(False, json_mode, f"Target worktree already exists: {target_path}")

    # Check source exists
    if not source_path.exists():
        return _output_result(False, json_mode, f"Source path does not exist: {source_path}")

    # Create new worktree from source
    success = ensure_worktree(
        source_path,  # Use source as base for the worktree
        target_branch,
        target_path,
        auto_create_branch=True,
    )
    if not success:
        # Try from project path instead
        if project_path.exists():
            success = ensure_worktree(
                project_path,
                target_branch,
                target_path,
                auto_create_branch=True,
            )

    if not success:
        return _output_result(False, json_mode, f"Failed to create worktree for branch '{target_branch}'")

    # Create new session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", target_session, "-c", str(target_path)],
        check=True
    )

    subprocess.run(
        ["tmux", "send-keys", "-t", target_session, f"export AGENTWIRE_ROOM={target_session}", "Enter"],
        check=True
    )
    time.sleep(0.1)

    if getattr(args, 'no_bypass', False):
        claude_cmd = "claude"
    else:
        claude_cmd = "claude --dangerously-skip-permissions"

    subprocess.run(
        ["tmux", "send-keys", "-t", target_session, claude_cmd, "Enter"],
        check=True
    )

    # Update rooms.json
    rooms_file = Path.home() / ".agentwire" / "rooms.json"
    rooms_file.parent.mkdir(parents=True, exist_ok=True)

    configs = {}
    if rooms_file.exists():
        try:
            with open(rooms_file) as f:
                configs = json.load(f)
        except Exception:
            pass

    bypass_permissions = not getattr(args, 'no_bypass', False)
    configs[target_session] = {"bypass_permissions": bypass_permissions}

    with open(rooms_file, "w") as f:
        json.dump(configs, f, indent=2)

    if json_mode:
        _output_json({
            "success": True,
            "session": target_session,
            "path": str(target_path),
            "branch": target_branch,
            "machine": None,
            "forked_from": source_full,
        })
    else:
        print(f"Forked '{source_full}' to '{target_session}'")
        print(f"  Path: {target_path}")
        print(f"Attach with: tmux attach -t {target_session}")

    return 0


# === Machine Commands ===

def cmd_machine_add(args) -> int:
    """Add a machine to the AgentWire network."""
    machine_id = args.machine_id
    host = args.host or machine_id  # Default host to id if not specified
    user = args.user
    projects_dir = args.projects_dir

    machines_file = CONFIG_DIR / "machines.json"
    machines_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing machines
    machines = []
    if machines_file.exists():
        try:
            with open(machines_file) as f:
                machines = json.load(f).get("machines", [])
        except (json.JSONDecodeError, IOError):
            pass

    # Check for duplicate ID
    if any(m.get("id") == machine_id for m in machines):
        print(f"Machine '{machine_id}' already exists", file=sys.stderr)
        return 1

    # Build machine entry
    new_machine = {"id": machine_id, "host": host}
    if user:
        new_machine["user"] = user
    if projects_dir:
        new_machine["projects_dir"] = projects_dir

    machines.append(new_machine)

    # Save
    with open(machines_file, "w") as f:
        json.dump({"machines": machines}, f, indent=2)
        f.write("\n")

    print(f"Added machine '{machine_id}'")
    print(f"  Host: {host}")
    if user:
        print(f"  User: {user}")
    if projects_dir:
        print(f"  Projects: {projects_dir}")
    print()
    print("Next steps:")
    print("  1. Ensure SSH access: ssh", f"{user}@{host}" if user else host)
    print("  2. Start tunnel: autossh -M 0 -f -N -R 8765:localhost:8765", machine_id)
    print("  3. Restart portal: agentwire portal stop && agentwire portal start")
    print()
    print("For full setup guide, run: /machine-setup in a Claude session")

    return 0


def cmd_machine_remove(args) -> int:
    """Remove a machine from the AgentWire network."""
    machine_id = args.machine_id

    machines_file = CONFIG_DIR / "machines.json"
    rooms_file = CONFIG_DIR / "rooms.json"

    # Step 1: Load and check machines.json
    if not machines_file.exists():
        print(f"No machines.json found at {machines_file}", file=sys.stderr)
        return 1

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Invalid machines.json: {e}", file=sys.stderr)
        return 1

    machines = machines_data.get("machines", [])
    machine = next((m for m in machines if m.get("id") == machine_id), None)

    if not machine:
        print(f"Machine '{machine_id}' not found in machines.json", file=sys.stderr)
        print(f"Available machines: {', '.join(m.get('id', '?') for m in machines)}")
        return 1

    host = machine.get("host", machine_id)

    print(f"Removing machine '{machine_id}' (host: {host})...")
    print()

    # Step 2: Kill autossh tunnel
    print("Stopping tunnel...")
    result = subprocess.run(
        ["pkill", "-f", f"autossh.*{machine_id}"],
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"  ✓ Killed autossh tunnel for {machine_id}")
    else:
        # Also try by host if different from id
        if host != machine_id:
            result = subprocess.run(
                ["pkill", "-f", f"autossh.*{host}"],
                capture_output=True,
            )
            if result.returncode == 0:
                print(f"  ✓ Killed autossh tunnel for {host}")
            else:
                print(f"  - No tunnel running (or already stopped)")
        else:
            print(f"  - No tunnel running (or already stopped)")

    # Step 3: Remove from machines.json
    print("Updating machines.json...")
    machines_data["machines"] = [m for m in machines if m.get("id") != machine_id]
    with open(machines_file, "w") as f:
        json.dump(machines_data, f, indent=2)
        f.write("\n")
    print(f"  ✓ Removed '{machine_id}' from machines.json")

    # Step 4: Clean rooms.json
    print("Cleaning rooms.json...")
    if rooms_file.exists():
        try:
            with open(rooms_file) as f:
                rooms_data = json.load(f)

            # Find rooms matching *@machine_id pattern
            rooms_to_remove = [
                room for room in rooms_data.keys()
                if room.endswith(f"@{machine_id}")
            ]

            if rooms_to_remove:
                for room in rooms_to_remove:
                    del rooms_data[room]
                with open(rooms_file, "w") as f:
                    json.dump(rooms_data, f, indent=2)
                    f.write("\n")
                print(f"  ✓ Removed {len(rooms_to_remove)} room(s): {', '.join(rooms_to_remove)}")
            else:
                print(f"  - No room configs found for @{machine_id}")
        except json.JSONDecodeError:
            print(f"  - rooms.json is invalid, skipping")
    else:
        print(f"  - No rooms.json found")

    # Step 5: Print manual steps
    print()
    print("=" * 50)
    print("MANUAL STEPS REQUIRED:")
    print("=" * 50)
    print()
    print("1. Remove SSH config entry:")
    print(f"   Edit ~/.ssh/config and remove the 'Host {machine_id}' block")
    print()
    print("2. Remove from tunnel startup script (if using):")
    print(f"   Edit ~/.local/bin/agentwire-tunnels")
    print(f"   Remove '{machine_id}' from the MACHINES list")
    print()
    print("3. Delete GitHub deploy keys:")
    print(f"   gh repo deploy-key list --repo <user>/<repo>")
    print(f"   # Find keys titled '{machine_id}' and delete them:")
    print(f"   gh repo deploy-key delete <key-id> --repo <user>/<repo>")
    print()
    print("4. Destroy remote machine:")
    print(f"   Option A: Delete user only")
    print(f"     ssh root@<ip> 'pkill -u agentwire; userdel -r agentwire'")
    print(f"   Option B: Destroy the VM entirely via provider console")
    print()
    print("5. Restart portal to pick up changes:")
    print("   agentwire portal stop && agentwire portal start")
    print()

    return 0


def cmd_machine_list(args) -> int:
    """List registered machines."""
    machines_file = CONFIG_DIR / "machines.json"

    if not machines_file.exists():
        print("No machines registered.")
        print(f"  Config: {machines_file}")
        return 0

    try:
        with open(machines_file) as f:
            machines_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Invalid machines.json: {e}", file=sys.stderr)
        return 1

    machines = machines_data.get("machines", [])

    if not machines:
        print("No machines registered.")
        return 0

    print(f"Registered machines ({len(machines)}):")
    print()
    for m in machines:
        machine_id = m.get("id", "?")
        host = m.get("host", machine_id)
        projects_dir = m.get("projects_dir", "~")

        # Check if tunnel is running
        result = subprocess.run(
            ["pgrep", "-f", f"autossh.*{machine_id}"],
            capture_output=True,
        )
        tunnel_status = "✓ tunnel" if result.returncode == 0 else "✗ no tunnel"

        print(f"  {machine_id}")
        print(f"    Host: {host}")
        print(f"    Projects: {projects_dir}")
        print(f"    Status: {tunnel_status}")
        print()

    return 0


# === Dev Command ===

def cmd_dev(args) -> int:
    """Start or attach to the AgentWire dev/orchestrator session."""
    session_name = "agentwire"
    project_dir = Path.home() / "projects" / "agentwire"

    if tmux_session_exists(session_name):
        print(f"Dev session exists. Attaching to '{session_name}'...")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    # Get agent command from config
    config = load_config()
    agent_cmd = config.get("agent", {}).get("command", "claude --dangerously-skip-permissions")

    # Create session and start Claude Code
    print(f"Creating dev session '{session_name}' in {project_dir}...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name, "-c", str(project_dir),
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, agent_cmd, "Enter",
    ])

    print(f"Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


# === Init Command ===

def cmd_init(args) -> int:
    """Initialize AgentWire configuration with interactive wizard."""
    if args.quick:
        # Quick mode: use Python prompts (no Claude session)
        from .onboarding import run_onboarding
        return run_onboarding()

    # Full mode: spawn Claude session for guided setup
    session_name = "agentwire-setup"

    if tmux_session_exists(session_name):
        print(f"Setup session already exists. Attaching...")
        subprocess.run(["tmux", "attach-session", "-t", session_name])
        return 0

    # Create config directory first
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # The prompt to send to Claude for guided onboarding
    setup_prompt = '''/init'''

    print("Starting AgentWire setup wizard...")
    print("This will spawn a Claude session to guide you through configuration.\n")

    # Create tmux session
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
        "-c", str(Path.home() / "projects" / "agentwire"),
    ])

    # Start Claude
    subprocess.run([
        "tmux", "send-keys", "-t", session_name,
        "claude --dangerously-skip-permissions", "Enter",
    ])

    # Wait a moment for Claude to start
    import time
    time.sleep(2)

    # Send the setup prompt
    subprocess.run([
        "tmux", "send-keys", "-t", session_name,
        setup_prompt, "Enter",
    ])

    print("Attaching to setup session... (Ctrl+B D to detach)\n")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


def cmd_generate_certs(args) -> int:
    """Generate SSL certificates."""
    return generate_certs()


# === Listen Commands ===

def cmd_listen_start(args) -> int:
    """Start voice recording."""
    from .listen import start_recording
    return start_recording()


def cmd_listen_stop(args) -> int:
    """Stop recording, transcribe, send to session."""
    from .listen import stop_recording
    session = args.session or "agentwire"
    return stop_recording(session, voice_prompt=not args.no_prompt)


def cmd_listen_cancel(args) -> int:
    """Cancel current recording."""
    from .listen import cancel_recording
    return cancel_recording()


def cmd_listen_toggle(args) -> int:
    """Toggle recording (start if not recording, stop if recording)."""
    from .listen import is_recording, start_recording, stop_recording
    session = args.session or "agentwire"
    if is_recording():
        return stop_recording(session, voice_prompt=not args.no_prompt)
    else:
        return start_recording()


# === Voice Clone Commands ===

def cmd_voiceclone_start(args) -> int:
    """Start voice recording for cloning."""
    from .voiceclone import start_recording
    return start_recording()


def cmd_voiceclone_stop(args) -> int:
    """Stop recording and upload voice clone."""
    from .voiceclone import stop_recording
    return stop_recording(args.name)


def cmd_voiceclone_cancel(args) -> int:
    """Cancel current recording."""
    from .voiceclone import cancel_recording
    return cancel_recording()


def cmd_voiceclone_list(args) -> int:
    """List available voices."""
    from .voiceclone import list_voices
    return list_voices()


def cmd_voiceclone_delete(args) -> int:
    """Delete a voice."""
    from .voiceclone import delete_voice
    return delete_voice(args.name)


# === Rebuild/Uninstall Commands ===

UV_CACHE_DIR = Path.home() / ".cache" / "uv"


def cmd_rebuild(args) -> int:
    """Rebuild: clear uv cache, uninstall, reinstall from source.

    This is the correct way to pick up source changes when developing.
    `uv tool install . --force` does NOT work - it uses cached wheels.
    """
    print("Rebuilding agentwire-dev...")
    print()

    # Step 1: Clear uv cache
    if UV_CACHE_DIR.exists():
        print(f"Clearing uv cache ({UV_CACHE_DIR})...")
        shutil.rmtree(UV_CACHE_DIR)
        print("  ✓ Cache cleared")
    else:
        print("  - No cache to clear")

    # Step 2: Uninstall
    print("Uninstalling agentwire-dev...")
    result = subprocess.run(
        ["uv", "tool", "uninstall", "agentwire-dev"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✓ Uninstalled")
    else:
        # Might not be installed, that's fine
        print("  - Not installed (continuing)")

    # Step 3: Reinstall from current directory
    # Find the project root (where pyproject.toml is)
    project_root = Path(__file__).parent.parent
    if not (project_root / "pyproject.toml").exists():
        # Fallback: assume we're in ~/projects/agentwire
        project_root = Path.home() / "projects" / "agentwire"

    print(f"Installing from {project_root}...")
    result = subprocess.run(
        ["uv", "tool", "install", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ✗ Install failed: {result.stderr}", file=sys.stderr)
        return 1

    print("  ✓ Installed")
    print()
    print("Rebuild complete. New version is active.")
    return 0


def cmd_uninstall(args) -> int:
    """Uninstall: clear uv cache and remove agentwire-dev tool."""
    print("Uninstalling agentwire-dev...")
    print()

    # Step 1: Clear uv cache
    if UV_CACHE_DIR.exists():
        print(f"Clearing uv cache ({UV_CACHE_DIR})...")
        shutil.rmtree(UV_CACHE_DIR)
        print("  ✓ Cache cleared")
    else:
        print("  - No cache to clear")

    # Step 2: Uninstall
    print("Uninstalling tool...")
    result = subprocess.run(
        ["uv", "tool", "uninstall", "agentwire-dev"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✓ Uninstalled")
    else:
        print(f"  - {result.stderr.strip() or 'Not installed'}")

    print()
    print("Uninstall complete.")
    print("To reinstall: cd ~/projects/agentwire && uv tool install .")
    return 0


# === Skills Commands ===

CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"
CLAUDE_HOOKS_DIR = Path.home() / ".claude" / "hooks"


def get_skills_source() -> Path:
    """Get the path to the skills directory in the installed package."""
    # First try: skills directory inside the agentwire package
    package_dir = Path(__file__).parent
    skills_dir = package_dir / "skills"
    if skills_dir.exists():
        return skills_dir

    # Fallback: try importlib.resources (for installed packages)
    try:
        with importlib.resources.files("agentwire").joinpath("skills") as p:
            if p.exists():
                return Path(p)
    except (TypeError, FileNotFoundError):
        pass

    raise FileNotFoundError("Could not find skills directory in package")


def get_hooks_source() -> Path:
    """Get the path to the hooks directory in the installed package."""
    # First try: hooks directory inside the agentwire package
    package_dir = Path(__file__).parent
    hooks_dir = package_dir / "hooks"
    if hooks_dir.exists():
        return hooks_dir

    # Fallback: try importlib.resources (for installed packages)
    try:
        with importlib.resources.files("agentwire").joinpath("hooks") as p:
            if p.exists():
                return Path(p)
    except (TypeError, FileNotFoundError):
        pass

    raise FileNotFoundError("Could not find hooks directory in package")


def install_permission_hook(force: bool = False, copy: bool = False) -> bool:
    """Install the permission hook for Claude Code integration.

    Returns True if hook was installed/updated, False if skipped.
    """
    hook_name = "agentwire-permission.sh"

    try:
        hooks_source = get_hooks_source()
    except FileNotFoundError:
        print("  Warning: hooks directory not found, skipping hook installation")
        return False

    source_hook = hooks_source / hook_name
    if not source_hook.exists():
        print(f"  Warning: {hook_name} not found in package, skipping hook installation")
        return False

    # Create ~/.claude/hooks if it doesn't exist
    CLAUDE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    target_hook = CLAUDE_HOOKS_DIR / hook_name

    # Check if already installed
    if target_hook.exists():
        if target_hook.is_symlink():
            current_target = target_hook.resolve()
            if current_target == source_hook.resolve() and not force:
                return False  # Already correctly installed
        if not force:
            print(f"  Hook already exists at {target_hook}")
            return False

        # Remove existing
        target_hook.unlink()

    # Create symlink (preferred) or copy
    if copy:
        shutil.copy2(source_hook, target_hook)
    else:
        target_hook.symlink_to(source_hook)

    # Make executable
    target_hook.chmod(0o755)

    return True


def cmd_skills_install(args) -> int:
    """Install Claude Code skills for AgentWire integration."""
    target_dir = CLAUDE_SKILLS_DIR / "agentwire"

    try:
        source_dir = get_skills_source()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Create ~/.claude/skills if it doesn't exist
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # Check if already installed
    skills_already_installed = False
    if target_dir.exists():
        if target_dir.is_symlink():
            current_target = target_dir.resolve()
            if current_target == source_dir.resolve():
                print(f"Skills already installed (symlink to {source_dir})")
                skills_already_installed = True
            else:
                print(f"Existing symlink points to {current_target}")
        else:
            print(f"Skills directory already exists at {target_dir}")

        if not skills_already_installed:
            if not args.force:
                print("Use --force to overwrite")
                return 1

            # Remove existing
            if target_dir.is_symlink():
                target_dir.unlink()
            else:
                shutil.rmtree(target_dir)

    # Create symlink (preferred) or copy - unless already installed
    if not skills_already_installed:
        if args.copy:
            shutil.copytree(source_dir, target_dir)
            print(f"Copied skills to {target_dir}")
        else:
            target_dir.symlink_to(source_dir)
            print(f"Linked skills: {target_dir} -> {source_dir}")

    # Install permission hook
    hook_installed = install_permission_hook(force=args.force, copy=args.copy)
    if hook_installed:
        print(f"Installed permission hook to {CLAUDE_HOOKS_DIR / 'agentwire-permission.sh'}")

    print("\nClaude Code skills installed. Available commands:")
    print("  /sessions, /send, /output, /spawn, /new, /kill, /status, /jump")
    if hook_installed:
        print("\nPermission hook installed for normal session support.")
    return 0


def cmd_skills_uninstall(args) -> int:
    """Uninstall Claude Code skills."""
    target_dir = CLAUDE_SKILLS_DIR / "agentwire"
    hook_file = CLAUDE_HOOKS_DIR / "agentwire-permission.sh"

    skills_removed = False
    hook_removed = False

    if target_dir.exists():
        if target_dir.is_symlink():
            target_dir.unlink()
            print(f"Removed symlink: {target_dir}")
        else:
            shutil.rmtree(target_dir)
            print(f"Removed directory: {target_dir}")
        skills_removed = True

    if hook_file.exists():
        hook_file.unlink()
        print(f"Removed hook: {hook_file}")
        hook_removed = True

    if not skills_removed and not hook_removed:
        print("Skills and hooks not installed")

    return 0


def cmd_skills_status(args) -> int:
    """Check Claude Code skills installation status."""
    target_dir = CLAUDE_SKILLS_DIR / "agentwire"
    hook_file = CLAUDE_HOOKS_DIR / "agentwire-permission.sh"

    skills_installed = target_dir.exists()
    hook_installed = hook_file.exists()

    if not skills_installed:
        print("Skills: not installed")
        print(f"  Run 'agentwire skills install' to set up Claude Code integration")
    else:
        if target_dir.is_symlink():
            source = target_dir.resolve()
            print(f"Skills: installed (symlink)")
            print(f"  Location: {target_dir} -> {source}")
        else:
            print(f"Skills: installed (copy)")
            print(f"  Location: {target_dir}")

        # List available skills
        skill_files = list(target_dir.glob("*.md"))
        skill_files = [f for f in skill_files if f.name != "SKILL.md"]
        if skill_files:
            print(f"  Commands: {', '.join('/' + f.stem for f in sorted(skill_files))}")

    print()
    if hook_installed:
        if hook_file.is_symlink():
            source = hook_file.resolve()
            print(f"Permission hook: installed (symlink)")
            print(f"  Location: {hook_file} -> {source}")
        else:
            print(f"Permission hook: installed (copy)")
            print(f"  Location: {hook_file}")
    else:
        print("Permission hook: not installed")
        print("  (Required for normal session permission prompts)")

    return 0 if skills_installed else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="agentwire",
        description="Multi-room voice web interface for AI coding agents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # === init command ===
    init_parser = subparsers.add_parser("init", help="Interactive setup wizard")
    init_parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: use simple prompts instead of Claude session"
    )
    init_parser.set_defaults(func=cmd_init)

    # === portal command group ===
    portal_parser = subparsers.add_parser("portal", help="Manage the web portal")
    portal_subparsers = portal_parser.add_subparsers(dest="portal_command")

    # portal start
    portal_start = portal_subparsers.add_parser(
        "start", help="Start portal in tmux session"
    )
    portal_start.add_argument("--config", type=Path, help="Config file path")
    portal_start.add_argument("--port", type=int, help="Override port")
    portal_start.add_argument("--host", type=str, help="Override host")
    portal_start.add_argument("--no-tts", action="store_true", help="Disable TTS")
    portal_start.add_argument("--no-stt", action="store_true", help="Disable STT")
    portal_start.add_argument("--dev", action="store_true",
                              help="Run from source (uv run) - picks up code changes")
    portal_start.set_defaults(func=cmd_portal_start)

    # portal serve (run in foreground)
    portal_serve = portal_subparsers.add_parser(
        "serve", help="Run portal in foreground"
    )
    portal_serve.add_argument("--config", type=Path, help="Config file path")
    portal_serve.add_argument("--port", type=int, help="Override port")
    portal_serve.add_argument("--host", type=str, help="Override host")
    portal_serve.add_argument("--no-tts", action="store_true", help="Disable TTS")
    portal_serve.add_argument("--no-stt", action="store_true", help="Disable STT")
    portal_serve.set_defaults(func=cmd_portal_serve)

    # portal stop
    portal_stop = portal_subparsers.add_parser("stop", help="Stop the portal")
    portal_stop.set_defaults(func=cmd_portal_stop)

    # portal status
    portal_status = portal_subparsers.add_parser("status", help="Check portal status")
    portal_status.set_defaults(func=cmd_portal_status)

    # portal generate-certs
    portal_certs = portal_subparsers.add_parser(
        "generate-certs", help="Generate SSL certificates"
    )
    portal_certs.set_defaults(func=cmd_generate_certs)

    # === tts command group ===
    tts_parser = subparsers.add_parser("tts", help="Manage TTS server")
    tts_subparsers = tts_parser.add_subparsers(dest="tts_command")

    # tts start
    tts_start = tts_subparsers.add_parser("start", help="Start TTS server in tmux")
    tts_start.add_argument("--port", type=int, help="Server port (default: 8100)")
    tts_start.add_argument("--host", type=str, help="Server host (default: 0.0.0.0)")
    tts_start.set_defaults(func=cmd_tts_start)

    # tts serve (run in foreground)
    tts_serve = tts_subparsers.add_parser("serve", help="Run TTS server in foreground")
    tts_serve.add_argument("--port", type=int, help="Server port (default: 8100)")
    tts_serve.add_argument("--host", type=str, help="Server host (default: 0.0.0.0)")
    tts_serve.set_defaults(func=cmd_tts_serve)

    # tts stop
    tts_stop = tts_subparsers.add_parser("stop", help="Stop TTS server")
    tts_stop.set_defaults(func=cmd_tts_stop)

    # tts status
    tts_status = tts_subparsers.add_parser("status", help="Check TTS status")
    tts_status.set_defaults(func=cmd_tts_status)

    # === say command ===
    say_parser = subparsers.add_parser("say", help="Speak text via TTS")
    say_parser.add_argument("text", nargs="*", help="Text to speak")
    say_parser.add_argument("--voice", type=str, help="Voice name")
    say_parser.add_argument("--room", type=str, help="Send to room (remote-say)")
    say_parser.add_argument("--exaggeration", type=float, help="Voice exaggeration (0-1)")
    say_parser.add_argument("--cfg", type=float, help="CFG weight (0-1)")
    say_parser.set_defaults(func=cmd_say)

    # === send command ===
    send_parser = subparsers.add_parser("send", help="Send prompt to a session (adds Enter)")
    send_parser.add_argument("-s", "--session", required=True, help="Target session (supports session@machine)")
    send_parser.add_argument("prompt", nargs="*", help="Prompt to send")
    send_parser.set_defaults(func=cmd_send)

    # === send-keys command ===
    send_keys_parser = subparsers.add_parser(
        "send-keys", help="Send raw keys to a session (with pause between groups)"
    )
    send_keys_parser.add_argument("-s", "--session", required=True, help="Target session (supports session@machine)")
    send_keys_parser.add_argument("keys", nargs="*", help="Key groups to send (e.g., 'hello world' Enter)")
    send_keys_parser.set_defaults(func=cmd_send_keys)

    # === list command (top-level) ===
    list_parser = subparsers.add_parser("list", help="List all tmux sessions (local + remote)")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.add_argument("--local", action="store_true", help="Only show local sessions")
    list_parser.set_defaults(func=cmd_list)

    # === new command (top-level) ===
    new_parser = subparsers.add_parser("new", help="Create new Claude Code session")
    new_parser.add_argument("-s", "--session", required=True, help="Session name (project, project/branch, or project/branch@machine)")
    new_parser.add_argument("-p", "--path", help="Working directory (default: ~/projects/<name>)")
    new_parser.add_argument("-f", "--force", action="store_true", help="Replace existing session")
    new_parser.add_argument("--no-bypass", action="store_true", help="Don't use --dangerously-skip-permissions (normal mode)")
    new_parser.add_argument("--restricted", action="store_true", help="Restricted mode: only allow say/remote-say commands (implies --no-bypass)")
    new_parser.add_argument("--json", action="store_true", help="Output as JSON")
    new_parser.set_defaults(func=cmd_new)

    # === output command (top-level) ===
    output_parser = subparsers.add_parser("output", help="Read session output")
    output_parser.add_argument("-s", "--session", required=True, help="Session name (supports session@machine)")
    output_parser.add_argument("-n", "--lines", type=int, default=50, help="Lines to show (default: 50)")
    output_parser.set_defaults(func=cmd_output)

    # === kill command (top-level) ===
    kill_parser = subparsers.add_parser("kill", help="Kill a session (clean shutdown)")
    kill_parser.add_argument("-s", "--session", required=True, help="Session name (supports session@machine)")
    kill_parser.set_defaults(func=cmd_kill)

    # === recreate command (top-level) ===
    recreate_parser = subparsers.add_parser("recreate", help="Destroy and recreate session with fresh worktree")
    recreate_parser.add_argument("-s", "--session", required=True, help="Session name (project/branch or project/branch@machine)")
    recreate_parser.add_argument("--no-bypass", action="store_true", help="Don't use --dangerously-skip-permissions")
    recreate_parser.add_argument("--json", action="store_true", help="Output as JSON")
    recreate_parser.set_defaults(func=cmd_recreate)

    # === fork command (top-level) ===
    fork_parser = subparsers.add_parser("fork", help="Fork a session into a new worktree")
    fork_parser.add_argument("-s", "--source", required=True, help="Source session (project or project/branch)")
    fork_parser.add_argument("-t", "--target", required=True, help="Target session (must include branch: project/new-branch)")
    fork_parser.add_argument("--no-bypass", action="store_true", help="Don't use --dangerously-skip-permissions")
    fork_parser.add_argument("--json", action="store_true", help="Output as JSON")
    fork_parser.set_defaults(func=cmd_fork)

    # === session command group (legacy, kept for backwards compat) ===
    session_parser = subparsers.add_parser("session", help="Manage tmux sessions")
    session_subparsers = session_parser.add_subparsers(dest="session_command")

    # session new <name> [path]
    session_new = session_subparsers.add_parser(
        "new", help="Create new Claude Code session"
    )
    session_new.add_argument("name", help="Session name (dots become underscores)")
    session_new.add_argument("path", nargs="?", help="Working directory (default: ~/projects/<name>)")
    session_new.add_argument("--force", "-f", action="store_true", help="Replace existing session")
    session_new.set_defaults(func=cmd_session_new)

    # session list
    session_list = session_subparsers.add_parser("list", help="List all sessions")
    session_list.set_defaults(func=cmd_session_list)

    # session output <session> [lines]
    session_output = session_subparsers.add_parser("output", help="Read session output")
    session_output.add_argument("session", help="Session name")
    session_output.add_argument("--lines", "-n", type=int, default=50, help="Lines to show (default: 50)")
    session_output.set_defaults(func=cmd_session_output)

    # session kill <session>
    session_kill = session_subparsers.add_parser("kill", help="Kill a session")
    session_kill.add_argument("session", help="Session name")
    session_kill.set_defaults(func=cmd_session_kill)

    # === dev command ===
    dev_parser = subparsers.add_parser(
        "dev", help="Start/attach to dev orchestrator session"
    )
    dev_parser.set_defaults(func=cmd_dev)

    # === listen command group ===
    listen_parser = subparsers.add_parser("listen", help="Voice input recording")
    listen_parser.add_argument(
        "--session", "-s", type=str, default="agentwire",
        help="Target session (default: agentwire)"
    )
    listen_parser.add_argument(
        "--no-prompt", action="store_true",
        help="Don't prepend voice prompt hint"
    )
    listen_subparsers = listen_parser.add_subparsers(dest="listen_command")

    # listen start
    listen_start = listen_subparsers.add_parser("start", help="Start recording")
    listen_start.set_defaults(func=cmd_listen_start)

    # listen stop
    listen_stop = listen_subparsers.add_parser("stop", help="Stop and send")
    listen_stop.add_argument("--session", "-s", type=str, help="Target session")
    listen_stop.add_argument("--no-prompt", action="store_true")
    listen_stop.set_defaults(func=cmd_listen_stop)

    # listen cancel
    listen_cancel = listen_subparsers.add_parser("cancel", help="Cancel recording")
    listen_cancel.set_defaults(func=cmd_listen_cancel)

    # Default listen (no subcommand) = toggle
    listen_parser.set_defaults(func=cmd_listen_toggle)

    # === voiceclone command group ===
    voiceclone_parser = subparsers.add_parser(
        "voiceclone", help="Record and upload voice clones"
    )
    voiceclone_subparsers = voiceclone_parser.add_subparsers(dest="voiceclone_command")

    # voiceclone start
    voiceclone_start = voiceclone_subparsers.add_parser(
        "start", help="Start recording for voice clone"
    )
    voiceclone_start.set_defaults(func=cmd_voiceclone_start)

    # voiceclone stop <name>
    voiceclone_stop = voiceclone_subparsers.add_parser(
        "stop", help="Stop recording and upload as voice clone"
    )
    voiceclone_stop.add_argument("name", help="Name for the voice clone")
    voiceclone_stop.set_defaults(func=cmd_voiceclone_stop)

    # voiceclone cancel
    voiceclone_cancel = voiceclone_subparsers.add_parser(
        "cancel", help="Cancel current recording"
    )
    voiceclone_cancel.set_defaults(func=cmd_voiceclone_cancel)

    # voiceclone list
    voiceclone_list = voiceclone_subparsers.add_parser(
        "list", help="List available voices"
    )
    voiceclone_list.set_defaults(func=cmd_voiceclone_list)

    # voiceclone delete <name>
    voiceclone_delete = voiceclone_subparsers.add_parser(
        "delete", help="Delete a voice clone"
    )
    voiceclone_delete.add_argument("name", help="Name of voice to delete")
    voiceclone_delete.set_defaults(func=cmd_voiceclone_delete)

    # === machine command group ===
    machine_parser = subparsers.add_parser("machine", help="Manage remote machines")
    machine_subparsers = machine_parser.add_subparsers(dest="machine_command")

    # machine list
    machine_list = machine_subparsers.add_parser("list", help="List registered machines")
    machine_list.set_defaults(func=cmd_machine_list)

    # machine add <id>
    machine_add = machine_subparsers.add_parser(
        "add", help="Add a machine to the network"
    )
    machine_add.add_argument("machine_id", help="Machine ID (used in session names)")
    machine_add.add_argument("--host", help="SSH host (defaults to machine_id)")
    machine_add.add_argument("--user", help="SSH user")
    machine_add.add_argument("--projects-dir", dest="projects_dir", help="Projects directory on remote")
    machine_add.set_defaults(func=cmd_machine_add)

    # machine remove <id>
    machine_remove = machine_subparsers.add_parser(
        "remove", help="Remove a machine from the network"
    )
    machine_remove.add_argument("machine_id", help="Machine ID to remove")
    machine_remove.set_defaults(func=cmd_machine_remove)

    # === skills command group ===
    skills_parser = subparsers.add_parser(
        "skills", help="Manage Claude Code skills integration"
    )
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command")

    # skills install
    skills_install = skills_subparsers.add_parser(
        "install", help="Install Claude Code skills for AgentWire"
    )
    skills_install.add_argument(
        "--force", "-f", action="store_true", help="Overwrite existing installation"
    )
    skills_install.add_argument(
        "--copy", action="store_true", help="Copy files instead of symlinking"
    )
    skills_install.set_defaults(func=cmd_skills_install)

    # skills uninstall
    skills_uninstall = skills_subparsers.add_parser(
        "uninstall", help="Remove Claude Code skills"
    )
    skills_uninstall.set_defaults(func=cmd_skills_uninstall)

    # skills status
    skills_status = skills_subparsers.add_parser(
        "status", help="Check skills installation status"
    )
    skills_status.set_defaults(func=cmd_skills_status)

    # === generate-certs (top-level shortcut) ===
    certs_parser = subparsers.add_parser(
        "generate-certs", help="Generate SSL certificates"
    )
    certs_parser.set_defaults(func=cmd_generate_certs)

    # === rebuild command ===
    rebuild_parser = subparsers.add_parser(
        "rebuild", help="Clear uv cache and reinstall from source (for development)"
    )
    rebuild_parser.set_defaults(func=cmd_rebuild)

    # === uninstall command ===
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Clear uv cache and uninstall the tool"
    )
    uninstall_parser.set_defaults(func=cmd_uninstall)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "portal" and getattr(args, "portal_command", None) is None:
        portal_parser.print_help()
        return 0

    if args.command == "tts" and getattr(args, "tts_command", None) is None:
        tts_parser.print_help()
        return 0

    if args.command == "machine" and getattr(args, "machine_command", None) is None:
        machine_parser.print_help()
        return 0

    if args.command == "skills" and getattr(args, "skills_command", None) is None:
        skills_parser.print_help()
        return 0

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
