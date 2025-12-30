"""CLI entry point for AgentWire."""

import argparse
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


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="agentwire",
        description="Multi-room voice web interface for AI coding agents.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="Custom config file path",
    )
    parser.add_argument(
        "--port",
        type=int,
        metavar="PORT",
        help="Override server port",
    )
    parser.add_argument(
        "--host",
        type=str,
        metavar="HOST",
        help="Override server host",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable TTS (text-only mode)",
    )
    parser.add_argument(
        "--no-stt",
        action="store_true",
        help="Disable STT (typing-only mode)",
    )
    parser.add_argument(
        "--generate-certs",
        action="store_true",
        help="Generate self-signed SSL certs and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    if args.generate_certs:
        return generate_certs()

    # Import server module and run
    from .server import main as server_main

    server_main(
        config_path=str(args.config) if args.config else None,
        port=args.port,
        host=args.host,
        no_tts=args.no_tts,
        no_stt=args.no_stt,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
