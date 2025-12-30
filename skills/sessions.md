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
3. Read room config from `~/.agentwire/rooms.json` for role labels
4. For each remote machine, SSH and list their tmux sessions
5. Display formatted output grouped by machine with roles

## Output Format

```
Local sessions:
  agentwire (orchestrator): 1 window
  assistant (chatbot): 1 window
  api (worker): 2 windows
  random-session: 1 window

devbox-1:
  ml (worker): 3 windows

gpu-server: (offline)
```

Sessions show name, role (if configured), and window count. Offline machines are indicated.

Roles are determined from `~/.agentwire/rooms.json`:
- `agentwire` is always "orchestrator"
- Sessions with `chatbot_mode: true` show as "chatbot"
- Other configured sessions show as "worker"
- Sessions not in config show without a role label

## Implementation

```bash
#!/bin/bash

rooms_file="$HOME/.agentwire/rooms.json"

# Function to get role for a session name
get_role() {
  local name="$1"

  # agentwire is always orchestrator
  if [ "$name" = "agentwire" ]; then
    echo "orchestrator"
    return
  fi

  # Check rooms.json for config
  if [ -f "$rooms_file" ]; then
    local config=$(jq -r --arg n "$name" '.[$n] // empty' "$rooms_file" 2>/dev/null)
    if [ -n "$config" ]; then
      local is_chatbot=$(echo "$config" | jq -r '.chatbot_mode // false')
      if [ "$is_chatbot" = "true" ]; then
        echo "chatbot"
      else
        echo "worker"
      fi
      return
    fi
  fi

  # Not in config - no role
  echo ""
}

# Function to format session line with role
format_session() {
  local name="$1"
  local windows="$2"
  local role=$(get_role "$name")

  if [ -n "$role" ]; then
    echo "  $name ($role): $windows"
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
- Room roles configured in `~/.agentwire/rooms.json`
