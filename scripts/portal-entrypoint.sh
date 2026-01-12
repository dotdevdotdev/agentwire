#!/bin/bash
# Run portal and STT inside tmux sessions for monitoring via agentwire SSH

PORTAL_SESSION="agentwire-portal"
STT_SESSION="agentwire-stt"

# Start SSH server for remote access
/usr/sbin/sshd

# Start tmux server
tmux start-server

# Create session running the portal
tmux new-session -d -s "$PORTAL_SESSION" "agentwire portal serve"
echo "Portal running in tmux session: $PORTAL_SESSION"

# Create session running the STT server
tmux new-session -d -s "$STT_SESSION" "python3 -m agentwire.stt.stt_server"
echo "STT running in tmux session: $STT_SESSION"

echo "Monitor via: agentwire output -s <session>@<machine>"

# Keep container alive while portal session exists
while tmux has-session -t "$PORTAL_SESSION" 2>/dev/null; do
    sleep 5
done

echo "Portal session ended"
