---
name: workers
description: List active worker sessions spawned by this orchestrator.
---

# /workers

List all active worker sessions. Workers are sessions with `type: worker` in rooms.json.

## Usage

```
/workers
```

## Behavior

1. Read room configs from `~/.agentwire/rooms.json`
2. List local tmux sessions, filter to workers only
3. For each remote machine, SSH and list worker sessions
4. Display formatted output with status indicators

## Output Format

```
Worker Sessions:
  api/auth-work (running): ~/projects/api-worktrees/auth-work
  api/test-suite (idle 2m): ~/projects/api-worktrees/test-suite

Remote (devbox-1):
  ml/training (running): ~/projects/ml-worktrees/training

No workers on: gpu-server (offline)
```

Workers show:
- Session name (usually project/task format)
- Status: running (output in last 10s) or idle (with duration)
- Working directory

## Implementation

```bash
#!/bin/bash

rooms_file="$HOME/.agentwire/rooms.json"
machines_file="$HOME/.agentwire/machines.json"

# Function to check if session is a worker
is_worker() {
  local name="$1"
  if [ -f "$rooms_file" ]; then
    local session_type=$(jq -r --arg n "$name" '.[$n].type // empty' "$rooms_file" 2>/dev/null)
    [ "$session_type" = "worker" ]
    return $?
  fi
  return 1
}

# Function to get session path
get_session_path() {
  local name="$1"
  if [ -f "$rooms_file" ]; then
    jq -r --arg n "$name" '.[$n].path // empty' "$rooms_file" 2>/dev/null
  fi
}

# Function to check if session has recent output (activity detection)
is_session_active() {
  local name="$1"
  # Capture pane content, check if there's been recent activity
  # This is a simple heuristic - could be improved
  local output=$(tmux capture-pane -t "$name" -p 2>/dev/null | tail -5)
  [ -n "$output" ]
}

echo "Worker Sessions:"

found_workers=false
local_sessions=$(tmux list-sessions -F "#{session_name}" 2>/dev/null)

if [ -n "$local_sessions" ]; then
  while read -r name; do
    if is_worker "$name"; then
      found_workers=true
      local path=$(get_session_path "$name")
      local status="running"  # Could add more sophisticated activity detection
      if [ -n "$path" ]; then
        echo "  $name ($status): $path"
      else
        echo "  $name ($status)"
      fi
    fi
  done <<< "$local_sessions"
fi

if [ "$found_workers" = "false" ]; then
  echo "  (no local workers)"
fi

# Check remote machines
if [ -f "$machines_file" ]; then
  machine_ids=$(jq -r '.machines[].id' "$machines_file" 2>/dev/null)

  for machine_id in $machine_ids; do
    host=$(jq -r --arg id "$machine_id" '.machines[] | select(.id == $id) | .host' "$machines_file" 2>/dev/null)

    remote_sessions=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" \
      "tmux list-sessions -F '#{session_name}'" 2>/dev/null)
    ssh_status=$?

    if [ $ssh_status -eq 0 ]; then
      remote_workers=""
      if [ -n "$remote_sessions" ]; then
        while read -r name; do
          # Check rooms.json for remote session (format: name@machine)
          room_key="${name}@${machine_id}"
          session_type=$(jq -r --arg n "$room_key" '.[$n].type // empty' "$rooms_file" 2>/dev/null)
          if [ "$session_type" = "worker" ]; then
            path=$(jq -r --arg n "$room_key" '.[$n].path // empty' "$rooms_file" 2>/dev/null)
            if [ -z "$remote_workers" ]; then
              echo ""
              echo "Remote ($machine_id):"
              remote_workers="found"
            fi
            if [ -n "$path" ]; then
              echo "  $name (running): $path"
            else
              echo "  $name (running)"
            fi
          fi
        done <<< "$remote_sessions"
      fi
      if [ -z "$remote_workers" ]; then
        echo ""
        echo "No workers on: $machine_id"
      fi
    else
      echo ""
      echo "No workers on: $machine_id (offline)"
    fi
  done
fi
```

## Notes

- Only shows sessions with `type: worker` in rooms.json
- Default sessions (no type) are NOT shown (they're orchestrators)
- Useful for orchestrator sessions to monitor spawned workers
- Use `/output <worker>` to check specific worker progress
- Use `/send <worker> "prompt"` to give workers new instructions
