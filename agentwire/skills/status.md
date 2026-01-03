---
name: status
description: Check status of all machines and list their sessions.
---

# /status

Check all machines and list active tmux sessions grouped by role.

## Usage

```
/status
```

No arguments needed - checks all configured machines.

## Behavior

1. **Collect Sessions**
   - List local tmux sessions with window counts
   - Check remote machines (from `~/.agentwire/machines.json`)
   - Test SSH connectivity with 5-second timeout

2. **Categorize by Role**
   - Read `~/.agentwire/rooms.json` for session configuration
   - Sessions with `chatbot_mode: true` → Chatbots
   - Session named `agentwire` → Orchestrator
   - Other configured sessions → Workers
   - Sessions not in rooms.json → Unconfigured

3. **Display grouped output**

## Example Output

```
Orchestrator:
  agentwire: 1 window (active)

Workers:
  api: 2 windows
  auth: 1 window

Chatbots:
  assistant: 1 window

Unconfigured:
  random-session: 1 window
```

## Implementation

```bash
#!/bin/bash
# Status check - sessions grouped by role

ROOMS_FILE=~/.agentwire/rooms.json
MACHINES_FILE=~/.agentwire/machines.json

# Arrays to hold sessions by category
declare -a orchestrator=()
declare -a workers=()
declare -a chatbots=()
declare -a unconfigured=()

# Get session info: "name:windows:active"
get_local_sessions() {
    tmux list-sessions -F "#{session_name}:#{session_windows}:#{?session_attached,active,}" 2>/dev/null
}

get_remote_sessions() {
    local host=$1
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" \
        "tmux list-sessions -F '#{session_name}:#{session_windows}:#{?session_attached,active,}'" 2>/dev/null
}

# Check if session is a chatbot
is_chatbot() {
    local session=$1
    if [[ -f "$ROOMS_FILE" ]]; then
        jq -e --arg s "$session" '.[$s].chatbot_mode == true' "$ROOMS_FILE" &>/dev/null
        return $?
    fi
    return 1
}

# Check if session is configured in rooms.json
is_configured() {
    local session=$1
    if [[ -f "$ROOMS_FILE" ]]; then
        jq -e --arg s "$session" 'has($s)' "$ROOMS_FILE" &>/dev/null
        return $?
    fi
    return 1
}

# Format session line
format_session() {
    local name=$1
    local windows=$2
    local active=$3
    local suffix=""
    [[ "$windows" == "1" ]] && suffix="window" || suffix="windows"
    [[ -n "$active" ]] && suffix="$suffix (active)"
    echo "  $name: $windows $suffix"
}

# Categorize a session
categorize_session() {
    local info=$1
    local name=$(echo "$info" | cut -d: -f1)
    local windows=$(echo "$info" | cut -d: -f2)
    local active=$(echo "$info" | cut -d: -f3)
    local line=$(format_session "$name" "$windows" "$active")

    if [[ "$name" == "agentwire" ]]; then
        orchestrator+=("$line")
    elif is_chatbot "$name"; then
        chatbots+=("$line")
    elif is_configured "$name"; then
        workers+=("$line")
    else
        unconfigured+=("$line")
    fi
}

# Collect local sessions
for session_info in $(get_local_sessions); do
    categorize_session "$session_info"
done

# Collect remote sessions
if [[ -f "$MACHINES_FILE" ]]; then
    hosts=$(jq -r '.machines[].host' "$MACHINES_FILE" 2>/dev/null)
    for host in $hosts; do
        for session_info in $(get_remote_sessions "$host"); do
            categorize_session "$session_info"
        done
    done
fi

# Print grouped output
if [[ ${#orchestrator[@]} -gt 0 ]]; then
    echo "Orchestrator:"
    printf '%s\n' "${orchestrator[@]}"
    echo ""
fi

if [[ ${#workers[@]} -gt 0 ]]; then
    echo "Workers:"
    printf '%s\n' "${workers[@]}"
    echo ""
fi

if [[ ${#chatbots[@]} -gt 0 ]]; then
    echo "Chatbots:"
    printf '%s\n' "${chatbots[@]}"
    echo ""
fi

if [[ ${#unconfigured[@]} -gt 0 ]]; then
    echo "Unconfigured:"
    printf '%s\n' "${unconfigured[@]}"
fi
```

## Configuration

**rooms.json** (`~/.agentwire/rooms.json`):

```json
{
  "assistant": {
    "voice": "default",
    "chatbot_mode": true
  },
  "api": {
    "path": "~/projects/api"
  }
}
```

**machines.json** (`~/.agentwire/machines.json`):

```json
{
  "machines": [
    {
      "id": "gpu-server",
      "host": "gpu-server"
    }
  ]
}
```

## Notes

- `agentwire` session is always categorized as Orchestrator
- Sessions with `chatbot_mode: true` in rooms.json are Chatbots
- Other sessions in rooms.json are Workers
- Sessions not in rooms.json are Unconfigured
- Uses `BatchMode=yes` to prevent SSH password prompts
- 5-second timeout prevents hanging on unreachable machines
