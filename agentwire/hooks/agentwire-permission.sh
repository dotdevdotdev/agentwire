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

# Get portal URL
# Priority: 1. AGENTWIRE_URL env var, 2. ~/.agentwire/portal_url file, 3. localhost
if [ -n "${AGENTWIRE_URL:-}" ]; then
    base_url="$AGENTWIRE_URL"
elif [ -f "$HOME/.agentwire/portal_url" ]; then
    base_url=$(cat "$HOME/.agentwire/portal_url" | tr -d '\n')
else
    base_url="https://localhost:8765"
fi

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
