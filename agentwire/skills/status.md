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

2. **Categorize by Permission Mode**
   - Read `~/.agentwire/sessions.json` for session configuration
   - Session named `agentwire` → Agentwire (main)
   - Sessions with `bypass_permissions: true` → Bypass Sessions
   - Sessions with `bypass_permissions: false` → Normal Sessions
   - Sessions not in sessions.json → Unconfigured

3. **Display grouped output**

## Example Output

```
Agentwire:
  agentwire: 1 window (active)

Bypass Sessions:
  api: 2 windows
  auth: 1 window

Normal Sessions:
  untrusted-lib: 1 window

Unconfigured:
  random-session: 1 window
```

## Implementation

```bash
#!/bin/bash
# Status check - sessions grouped by role

SESSIONS_FILE=~/.agentwire/sessions.json
MACHINES_FILE=~/.agentwire/machines.json

# Arrays to hold sessions by category
declare -a agentwire_sessions=()
declare -a bypass_sessions=()
declare -a normal_sessions=()
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

# Check if session has bypass_permissions enabled (default: true for backwards compat)
has_bypass_permissions() {
    local session=$1
    if [[ -f "$SESSIONS_FILE" ]]; then
        # Return true if bypass_permissions is true or not set (defaults to true)
        local val=$(jq -r --arg s "$session" '.[$s].bypass_permissions // true' "$SESSIONS_FILE" 2>/dev/null)
        [[ "$val" == "true" ]]
        return $?
    fi
    return 0  # Default to bypass if no config
}

# Check if session is configured in sessions.json
is_configured() {
    local session=$1
    if [[ -f "$SESSIONS_FILE" ]]; then
        jq -e --arg s "$session" 'has($s)' "$SESSIONS_FILE" &>/dev/null
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
        agentwire_sessions+=("$line")
    elif is_configured "$name"; then
        if has_bypass_permissions "$name"; then
            bypass_sessions+=("$line")
        else
            normal_sessions+=("$line")
        fi
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
if [[ ${#agentwire_sessions[@]} -gt 0 ]]; then
    echo "Agentwire:"
    printf '%s\n' "${agentwire_sessions[@]}"
    echo ""
fi

if [[ ${#bypass_sessions[@]} -gt 0 ]]; then
    echo "Bypass Sessions:"
    printf '%s\n' "${bypass_sessions[@]}"
    echo ""
fi

if [[ ${#normal_sessions[@]} -gt 0 ]]; then
    echo "Normal Sessions:"
    printf '%s\n' "${normal_sessions[@]}"
    echo ""
fi

if [[ ${#unconfigured[@]} -gt 0 ]]; then
    echo "Unconfigured:"
    printf '%s\n' "${unconfigured[@]}"
fi
```

## Configuration

**sessions.json** (`~/.agentwire/sessions.json`):

```json
{
  "api": {
    "voice": "default",
    "bypass_permissions": true
  },
  "untrusted-lib": {
    "voice": "default",
    "bypass_permissions": false
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
- Sessions with `bypass_permissions: true` (or unset, defaults to true) are Bypass Sessions
- Sessions with `bypass_permissions: false` are Normal Sessions (permission prompts enabled)
- Sessions not in sessions.json are Unconfigured
- Uses `BatchMode=yes` to prevent SSH password prompts
- 5-second timeout prevents hanging on unreachable machines
