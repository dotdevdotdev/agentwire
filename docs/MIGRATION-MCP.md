# Migration Guide: say/remote-say → MCP Tools

> Moving from shell scripts to native MCP server integration for voice capabilities.

## Overview

AgentWire has transitioned from shell-based voice commands (`say`/`remote-say`) to native MCP server integration. This provides better reliability, automatic session detection, and eliminates installation issues.

## What's Changing

### Deprecated (Old Approach)

```bash
# Shell scripts requiring PATH installation
say "Hello world"           # Local TTS
remote-say "Task complete"  # Remote TTS via portal
```

**Problems with this approach:**
- Requires installation in `~/.local/bin` and PATH configuration
- Installation issues documented in case studies (~/.local/bin not in PATH)
- Depends on AGENTWIRE_ROOM env var being set correctly
- Remote machines need portal_url configured
- Portal must be running for remote-say to work
- Silent failures if portal is down
- Instruction-based (agents must "know" to use them)

### Recommended (New Approach)

```python
# Native MCP tools auto-discovered by Claude Code
speak("Hello world")           # Auto-routes to appropriate TTS
speak("Task complete", voice="bashbunni")  # With voice selection
```

**Benefits:**
- Native tool integration (Claude Code auto-discovers)
- Always available (background daemon)
- Works without portal running (local TTS fallback)
- Auto-detects calling session (no AGENTWIRE_ROOM needed)
- Proper error messages (not silent failures)
- No installation per session (MCP configured once globally)
- No PATH issues (MCP handles routing)

## Migration Steps

### 1. Install MCP Server (One-Time Setup)

```bash
# Register MCP server with Claude Code
agentwire skills install

# Start the daemon
agentwire daemon start

# Verify daemon is running
agentwire daemon status
```

### 2. Update Your Workflow

**Before (shell scripts):**
```bash
# In session, need AGENTWIRE_ROOM set correctly
export AGENTWIRE_ROOM="myproject"
say "Building the project"
remote-say "Build complete"
```

**After (MCP tools):**
```python
# No setup needed - just use the tool
speak("Building the project")
speak("Build complete")  # Auto-routes to portal if room exists
```

### 3. Update Custom Scripts (If Any)

If you have custom scripts or instructions that use `say`/`remote-say`:

**Before:**
```bash
#!/bin/bash
# build.sh
./build.sh && say "Build successful"
```

**After:**
```bash
#!/bin/bash
# build.sh
./build.sh && agentwire say "Build successful"
# Or better: let Claude Code use speak() tool directly
```

**Note:** For scripts, you can use `agentwire say` CLI command which still works. But for Claude Code sessions, use the MCP `speak()` tool.

## MCP Tools Reference

### speak(text, voice=None)

Speak text via TTS with automatic routing.

**Parameters:**
- `text` (required): Text to speak
- `voice` (optional): Voice name (defaults to session's configured voice)

**Examples:**
```python
speak("Task complete")
speak("Error in line 42", voice="bashbunni")
speak("Build finished, check the output")
```

**Routing logic:**
1. Daemon detects calling session (PID → tmux → room name)
2. If room exists and portal is running → broadcasts to browser
3. Otherwise → uses configured TTS backend from config.yaml
4. Respects user's backend setting (chatterbox/openai/none)

### list_voices()

List available TTS voices.

**Returns:** List of voice names

**Example:**
```python
voices = list_voices()
# ['bashbunni', 'default', 'custom-voice-1', ...]
```

### set_voice(name)

Set default voice for this session.

**Parameters:**
- `name` (required): Voice name from list_voices()

**Example:**
```python
set_voice("bashbunni")
speak("Now using bashbunni voice")
```

**Note:** This persists to `~/.agentwire/rooms.json` for the detected session.

## Daemon Management

### Starting the Daemon

```bash
# Start in background
agentwire daemon start

# Check status
agentwire daemon status
# Output: Daemon running (PID: 12345)

# View logs
agentwire daemon logs
```

### Stopping the Daemon

```bash
agentwire daemon stop
```

### Restarting the Daemon

```bash
agentwire daemon restart
```

## Troubleshooting

### Daemon Not Running

**Symptom:** MCP tools not available in Claude Code

**Solution:**
```bash
# Check daemon status
agentwire daemon status

# If not running, start it
agentwire daemon start

# Verify it started
agentwire daemon status
```

### Session Detection Fails

**Symptom:** Voice goes to wrong session or uses system TTS instead of portal

**Diagnosis:**
```bash
# Check daemon logs
agentwire daemon logs

# Look for session detection messages
```

**Common causes:**
- Session not created via AgentWire CLI (no AGENTWIRE_ROOM env var fallback)
- Running outside tmux (daemon can't detect session)
- Process tree doesn't contain tmux parent

**Solution:**
- Always create sessions with `agentwire new -s <name>`
- If needed, set AGENTWIRE_ROOM manually: `export AGENTWIRE_ROOM="myproject"`

### Portal Not Receiving Voice

**Symptom:** Voice plays locally but doesn't broadcast to browser

**Check:**
1. Is portal running? `agentwire portal status`
2. Is room registered? Check dashboard at `https://localhost:8765`
3. Check daemon logs: `agentwire daemon logs`

**Solution:**
```bash
# Ensure portal is running
agentwire portal start

# Restart daemon to pick up portal
agentwire daemon restart
```

### TTS Backend Not Working

**Symptom:** No voice output at all

**Check config.yaml:**
```yaml
tts:
  backend: "chatterbox"  # or "none" if disabled
  url: "http://localhost:8100"
  default_voice: "bashbunni"
```

**Solutions:**
- If using Chatterbox, ensure it's running: `agentwire tts status`
- If backend is "none", change to "chatterbox" or another backend
- Check TTS server logs: `agentwire tts status`

### MCP Tools Not Auto-Discovered

**Symptom:** Claude Code doesn't see speak/list_voices/set_voice tools

**Check MCP registration:**
```bash
# List MCP servers
claude mcp list

# Should show:
# agentwire: agentwire daemon mcp
```

**Solution:**
```bash
# Re-register MCP server
agentwire skills install

# Restart Claude Code session
/exit
agentwire recreate -s <session>
```

## Comparing Approaches

| Feature | say/remote-say (Old) | MCP Tools (New) |
|---------|---------------------|----------------|
| **Installation** | Per-session PATH setup | One-time global setup |
| **Session detection** | Manual AGENTWIRE_ROOM env var | Automatic via PID → tmux |
| **Portal routing** | remote-say only | Automatic when room exists |
| **Fallback behavior** | Silent failure if portal down | Falls back to configured backend |
| **Error messages** | None (silent) | Proper error reporting |
| **Discovery** | Instruction-based | Auto-discovered by Claude |
| **Configuration** | portal_url file + env vars | Daemon handles routing |
| **Works offline** | say only (local) | Yes (local TTS fallback) |

## Timeline

- **Now:** Both approaches work (say/remote-say still functional)
- **Migration period:** Users transition to MCP tools
- **Future:** say/remote-say scripts may be removed in a future release

**Recommendation:** Migrate to MCP tools now to avoid future breaking changes.

## Getting Help

If you encounter issues during migration:

1. **Check daemon logs:** `agentwire daemon logs`
2. **Verify setup:** `agentwire daemon status`
3. **Test MCP tools:** In Claude Code, try `speak("test")`
4. **Check MCP registration:** `claude mcp list`

For additional help, see:
- [AgentWire Documentation](../CLAUDE.md)
- [TTS Setup Guide](../README.md#voice-integration)
- [Daemon Architecture](../docs/missions/agentwire-mcp-server.md)
