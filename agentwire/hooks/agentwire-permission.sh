#!/bin/bash
# AgentWire Permission Hook for Claude Code
#
# This script is called by Claude Code's hook system when a permission
# check is needed. It reads the permission request JSON from stdin,
# posts it to the AgentWire portal, and returns the decision.
#
# Environment:
#   AGENTWIRE_ROOM - The room name for this session (required)
#   AGENTWIRE_URL  - Base URL of the portal (default: https://localhost:8765)

set -e

# Read JSON from stdin
input=$(cat)

# Get room from environment
room="${AGENTWIRE_ROOM:-}"
if [ -z "$room" ]; then
    echo '{"decision": "deny", "message": "AGENTWIRE_ROOM environment variable not set"}' >&2
    exit 1
fi

# Get portal URL (default to localhost with HTTPS)
base_url="${AGENTWIRE_URL:-https://localhost:8765}"

# POST to portal and wait for response (5 minute timeout)
response=$(curl -s -X POST "${base_url}/api/permission/${room}" \
    -H "Content-Type: application/json" \
    -d "$input" \
    --max-time 300 \
    --insecure 2>/dev/null)

# Check if curl succeeded
if [ $? -ne 0 ]; then
    echo '{"decision": "deny", "message": "Failed to connect to AgentWire portal"}' >&2
    exit 1
fi

# Return the response
echo "$response"
