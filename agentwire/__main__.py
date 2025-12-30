"""CLI entry point for AgentWire."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__


def generate_certs() -> int:
    """Generate self-signed SSL certificates."""
    cert_dir = Path.home() / ".agentwire"
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
    """Check if a tmux session exists."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", name],
        capture_output=True,
    )
    return result.returncode == 0


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

    # Create session and start Claude Code
    print(f"Creating dev session '{session_name}' in {project_dir}...")
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session_name, "-c", str(project_dir),
    ])
    subprocess.run([
        "tmux", "send-keys", "-t", session_name, "claude", "Enter",
    ])

    print(f"Attaching... (Ctrl+B D to detach)")
    subprocess.run(["tmux", "attach-session", "-t", session_name])
    return 0


def cmd_generate_certs(args) -> int:
    """Generate SSL certificates."""
    return generate_certs()


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

    # === dev command ===
    dev_parser = subparsers.add_parser(
        "dev", help="Start/attach to dev orchestrator session"
    )
    dev_parser.set_defaults(func=cmd_dev)

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

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
