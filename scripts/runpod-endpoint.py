#!/usr/bin/env python3
"""Manage RunPod serverless endpoints for AgentWire TTS.

Prerequisites:
- RunPod account with API key
- Docker image pushed to Docker Hub (DOCKER_USERNAME/agentwire-tts:latest)

Usage:
    export RUNPOD_API_KEY=your_key_here
    export DOCKER_USERNAME=yourname

    # Create endpoint
    ./scripts/runpod-endpoint.py create

    # List endpoints
    ./scripts/runpod-endpoint.py list

    # Get endpoint details
    ./scripts/runpod-endpoint.py get <endpoint_id>

    # Delete endpoint
    ./scripts/runpod-endpoint.py delete <endpoint_id>
"""

import json
import os
import sys
from pathlib import Path

try:
    import runpod
except ImportError:
    print("ERROR: runpod SDK not installed")
    print("Install with: pip install runpod")
    sys.exit(1)


def get_config():
    """Get configuration from environment variables."""
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("ERROR: RUNPOD_API_KEY environment variable not set")
        sys.exit(1)

    docker_username = os.environ.get("DOCKER_USERNAME")
    if not docker_username:
        print("ERROR: DOCKER_USERNAME environment variable not set")
        sys.exit(1)

    return {
        "api_key": api_key,
        "docker_image": f"{docker_username}/agentwire-tts:latest",
    }


def create_endpoint(config):
    """Create a new RunPod serverless endpoint."""
    runpod.api_key = config["api_key"]

    print(f"Creating endpoint with image: {config['docker_image']}")

    # Create endpoint configuration
    endpoint_config = {
        "name": "agentwire-tts",
        "image_name": config["docker_image"],
        "gpu_ids": "AMPERE_16",  # RTX 3000/4000 series or A100
        "workers_min": 0,  # Scale to zero when idle
        "workers_max": 1,  # Max concurrent workers
        "execution_timeout": 180,  # 180 seconds max per request
        "idle_timeout": 180,  # Scale down after 180 seconds of inactivity
    }

    try:
        # Note: Actual RunPod SDK endpoint creation uses runpod.create_endpoint()
        # The exact API may vary - check RunPod docs for current SDK
        endpoint = runpod.create_endpoint(**endpoint_config)

        print("\n==> Endpoint created successfully!")
        print(f"    ID: {endpoint['id']}")
        print(f"    Name: {endpoint['name']}")
        print(f"    URL: {endpoint.get('url', 'N/A')}")

        # Save endpoint ID to file for easy reference
        endpoint_file = Path.home() / ".agentwire" / "runpod_endpoint.txt"
        endpoint_file.parent.mkdir(parents=True, exist_ok=True)
        endpoint_file.write_text(endpoint['id'])
        print(f"\n==> Endpoint ID saved to: {endpoint_file}")

        return endpoint
    except Exception as e:
        print(f"ERROR: Failed to create endpoint: {e}")
        sys.exit(1)


def list_endpoints(config):
    """List all RunPod endpoints."""
    runpod.api_key = config["api_key"]

    try:
        endpoints = runpod.get_endpoints()

        if not endpoints:
            print("No endpoints found")
            return

        print("\n==> RunPod Endpoints:")
        for ep in endpoints:
            print(f"\n  ID: {ep['id']}")
            print(f"  Name: {ep.get('name', 'N/A')}")
            print(f"  Image: {ep.get('image_name', 'N/A')}")
            print(f"  Workers: {ep.get('workers', {}).get('running', 0)}/{ep.get('workers', {}).get('max', 0)}")
            print(f"  URL: {ep.get('url', 'N/A')}")
    except Exception as e:
        print(f"ERROR: Failed to list endpoints: {e}")
        sys.exit(1)


def get_endpoint(config, endpoint_id):
    """Get details for a specific endpoint."""
    runpod.api_key = config["api_key"]

    try:
        endpoint = runpod.get_endpoint(endpoint_id)
        print(json.dumps(endpoint, indent=2))
    except Exception as e:
        print(f"ERROR: Failed to get endpoint: {e}")
        sys.exit(1)


def delete_endpoint(config, endpoint_id):
    """Delete a RunPod endpoint."""
    runpod.api_key = config["api_key"]

    print(f"Deleting endpoint: {endpoint_id}")

    try:
        runpod.delete_endpoint(endpoint_id)
        print("==> Endpoint deleted successfully!")

        # Remove saved endpoint ID if it matches
        endpoint_file = Path.home() / ".agentwire" / "runpod_endpoint.txt"
        if endpoint_file.exists() and endpoint_file.read_text().strip() == endpoint_id:
            endpoint_file.unlink()
            print(f"==> Removed saved endpoint ID from {endpoint_file}")
    except Exception as e:
        print(f"ERROR: Failed to delete endpoint: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    config = get_config()

    if command == "create":
        create_endpoint(config)
    elif command == "list":
        list_endpoints(config)
    elif command == "get":
        if len(sys.argv) < 3:
            print("ERROR: endpoint_id required")
            print("Usage: ./scripts/runpod-endpoint.py get <endpoint_id>")
            sys.exit(1)
        get_endpoint(config, sys.argv[2])
    elif command == "delete":
        if len(sys.argv) < 3:
            print("ERROR: endpoint_id required")
            print("Usage: ./scripts/runpod-endpoint.py delete <endpoint_id>")
            sys.exit(1)
        delete_endpoint(config, sys.argv[2])
    else:
        print(f"ERROR: Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
