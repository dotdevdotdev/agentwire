---
name: sessions
description: List all tmux sessions across local and remote machines.
---

# /sessions

List all tmux sessions running on local machine and configured remote machines.

## Usage

```
/sessions
```

## Behavior

1. List local tmux sessions with window count
2. Read machine list from `~/.agentwire/machines.json`
3. Read session config from `~/.agentwire/sessions.json` for role labels
4. For each remote machine, SSH and list their tmux sessions
5. Display formatted output grouped by machine with roles

## Output Format

```
Local sessions:
  agentwire (agentwire): 1 window
  api (bypass): 2 windows
  untrusted-lib (normal): 1 window
  random-session: 1 window

devbox-1:
  ml (bypass): 3 windows

gpu-server: (offline)
```

Sessions show name, permission mode (if configured), and window count. Offline machines are indicated.

Permission modes are determined from `~/.agentwire/sessions.json`:
- `agentwire` is always the main agentwire role
- Sessions with `bypass_permissions: true` (or unset) show as "bypass"
- Sessions with `bypass_permissions: false` show as "normal"
- Sessions not in config show without a label

## Implementation

```bash
#!/bin/bash

sessions_file="$HOME/.agentwire/sessions.json"

# Function to get permission mode for a session name
get_permission_mode() {
  local name="$1"

  # agentwire is always the main agentwire role
  if [ "$name" = "agentwire" ]; then
    echo "agentwire"
    return
  fi

  # Check sessions.json for config
  if [ -f "$sessions_file" ]; then
    local config=$(jq -r --arg n "$name" '.[$n] // empty' "$sessions_file" 2>/dev/null)
    if [ -n "$config" ]; then
      # bypass_permissions defaults to true if not set
      local bypass=$(echo "$config" | jq -r '.bypass_permissions // true')
      if [ "$bypass" = "true" ]; then
        echo "bypass"
      else
        echo "normal"
      fi
      return
    fi
  fi

  # Not in config - no label
  echo ""
}

# Function to format session line with permission mode
format_session() {
  local name="$1"
  local windows="$2"
  local mode=$(get_permission_mode "$name")

  if [ -n "$mode" ]; then
    echo "  $name ($mode): $windows"
  else
    echo "  $name: $windows"
  fi
}

echo "Local sessions:"
local_sessions=$(tmux list-sessions -F "#{session_name}|#{session_windows}" 2>/dev/null)
if [ -n "$local_sessions" ]; then
  while IFS='|' read -r name win_count; do
    if [ "$win_count" = "1" ]; then
      format_session "$name" "1 window"
    else
      format_session "$name" "$win_count windows"
    fi
  done <<< "$local_sessions"
else
  echo "  (no sessions)"
fi

# Read machines from config
machines_file="$HOME/.agentwire/machines.json"
if [ -f "$machines_file" ]; then
  hosts=$(jq -r '.machines[].host' "$machines_file" 2>/dev/null)

  for host in $hosts; do
    echo ""
    echo "$host:"
    remote_sessions=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" \
      "tmux list-sessions -F '#{session_name}|#{session_windows}'" 2>/dev/null)
    ssh_status=$?
    if [ $ssh_status -eq 0 ] && [ -n "$remote_sessions" ]; then
      while IFS='|' read -r name win_count; do
        if [ "$win_count" = "1" ]; then
          format_session "$name" "1 window"
        else
          format_session "$name" "$win_count windows"
        fi
      done <<< "$remote_sessions"
    elif [ $ssh_status -eq 0 ]; then
      echo "  (no sessions)"
    else
      echo "  (offline)"
    fi
  done
fi
```

## Notes

- Requires `jq` for JSON parsing
- SSH uses BatchMode to avoid password prompts
- 3-second timeout for unresponsive machines
- Machines configured in `~/.agentwire/machines.json`
- Permission modes configured in `~/.agentwire/sessions.json`
