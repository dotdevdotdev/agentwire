#!/bin/bash
# Run portal inside tmux session for monitoring via agentwire SSH

SESSION_NAME="agentwire-portal"

# Start SSH server for remote access
/usr/sbin/sshd

# Start tmux server
tmux start-server

# Create session running the portal
tmux new-session -d -s "$SESSION_NAME" "agentwire portal serve"

echo "Portal running in tmux session: $SESSION_NAME"
echo "Monitor via: agentwire output -s agentwire-portal@<machine>"

# Keep container alive while tmux session exists
while tmux has-session -t "$SESSION_NAME" 2>/dev/null; do
    sleep 5
done

echo "Portal session ended"
