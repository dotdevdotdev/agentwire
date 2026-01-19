#!/bin/bash
# AgentWire Permission Hook for Claude Code
#
# This script is called by Claude Code's hook system when a permission
# check is needed. It reads the permission request JSON from stdin,
# posts it to the AgentWire portal, and returns the decision.
#
# Session detection (no env vars required):
#   1. .agentwire.yml in current or parent directory
#   2. Infer from directory path (~/projects/{session})
#   3. tmux session name

set -e

# Read JSON from stdin
input=$(cat)

# Find .agentwire.yml in current or parent directories
find_agentwire_config() {
    local dir="$PWD"
    local home="$HOME"
    while [ "$dir" != "/" ] && [ "$dir" != "$home" ]; do
        if [ -f "$dir/.agentwire.yml" ]; then
            echo "$dir/.agentwire.yml"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

# Infer session from directory path
infer_session_from_path() {
    local cwd="$PWD"
    local projects_dir="$HOME/projects"
    if [[ "$cwd" == "$projects_dir"* ]]; then
        local rel_path="${cwd#$projects_dir/}"
        if [[ "$rel_path" =~ ^([^/]+)-worktrees/([^/]+) ]]; then
            echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
            return 0
        fi
        local project=$(echo "$rel_path" | cut -d'/' -f1)
        if [ -n "$project" ]; then
            echo "$project"
            return 0
        fi
    fi
    return 1
}

# Get session name
get_session() {
    # 1. tmux session name (most reliable - actual runtime context)
    if [ -n "$TMUX" ]; then
        tmux display-message -p '#S' 2>/dev/null
        return
    fi
    # 2. Infer from directory path (fallback when not in tmux)
    local inferred=$(infer_session_from_path)
    if [ -n "$inferred" ]; then
        echo "$inferred"
        return
    fi
    echo ""
}

session=$(get_session)
if [ -z "$session" ]; then
    echo '{"decision": "deny", "message": "Could not determine session (not in tmux, not in project dir)"}' >&2
    exit 1
fi

# Get portal URL from global config
# Priority: 1. ~/.agentwire/portal_url file, 2. config.yaml server section, 3. default
get_portal_url() {
    # Explicit portal_url file takes priority
    if [ -f "$HOME/.agentwire/portal_url" ]; then
        cat "$HOME/.agentwire/portal_url" | tr -d '\n'
        return
    fi
    # Try to read server.port from config.yaml
    if [ -f "$HOME/.agentwire/config.yaml" ]; then
        # Check if SSL is configured (look for cert under ssl section)
        local has_ssl=$(grep -A2 "^\s*ssl:" "$HOME/.agentwire/config.yaml" 2>/dev/null | grep -E "cert:" || true)
        local port=$(grep -E "^\s*port:" "$HOME/.agentwire/config.yaml" 2>/dev/null | head -1 | sed 's/.*port:[[:space:]]*//' | tr -d '"'"'" || true)
        if [ -n "$port" ]; then
            if [ -n "$has_ssl" ]; then
                echo "https://localhost:$port"
            else
                echo "http://localhost:$port"
            fi
            return
        fi
    fi
    # Default
    echo "https://localhost:8765"
}

base_url=$(get_portal_url)

# POST to portal and wait for response (5 minute timeout)
response=$(curl -s -X POST "${base_url}/api/permission/${session}" \
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
