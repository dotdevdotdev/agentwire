"""CLI entry point for AgentWire."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import __version__

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
    print(f"Starting AgentWire portal in tmux session '{session_name}'...")
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
    model = args.model or tts_config.get("model", "chatterbox")

    # Build chatterbox command
    # This assumes chatterbox is installed and available
    tts_cmd = f"chatterbox serve --port {port}"
    if args.gpu:
        tts_cmd += " --device cuda"

    print(f"Starting TTS server on port {port}...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name,
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, tts_cmd, "Enter",
    ])

    print(f"TTS server started. Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
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
        portal_url = config.get("server", {}).get("url", "https://localhost:8765")
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
    tts_start = tts_subparsers.add_parser("start", help="Start TTS server")
    tts_start.add_argument("--port", type=int, help="Server port (default: 8100)")
    tts_start.add_argument("--model", type=str, help="TTS model")
    tts_start.add_argument("--gpu", action="store_true", help="Use GPU acceleration")
    tts_start.set_defaults(func=cmd_tts_start)

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

    # === generate-certs (top-level shortcut) ===
    certs_parser = subparsers.add_parser(
        "generate-certs", help="Generate SSL certificates"
    )
    certs_parser.set_defaults(func=cmd_generate_certs)

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

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
