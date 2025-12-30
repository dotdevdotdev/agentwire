---
name: init
description: Interactive onboarding wizard for AgentWire setup. Walks users through all configuration options, handles existing configs, and fully sets up the system.
---

# /init - AgentWire Onboarding Wizard

Interactive setup wizard that configures AgentWire for the user's environment.

## Trigger

Run when user executes `agentwire init` from the CLI.

## Behavior

### 1. Detect Existing Configuration

First, check if `~/.agentwire/` exists and has configuration:

```bash
ls ~/.agentwire/config.yaml 2>/dev/null
```

**If config exists**, present options:
- **Review & Adjust** - Walk through current settings, offer to change specific sections
- **Start Fresh** - Back up existing config, create new from scratch
- **Cancel** - Exit without changes

**If no config exists**, proceed with fresh setup.

### 2. Welcome Message

```
Welcome to AgentWire Setup!

AgentWire is a multi-room voice interface for AI coding agents.
I'll walk you through configuring:

  1. Project directory (where your code projects live)
  2. Agent command (how to start Claude Code sessions)
  3. Text-to-Speech (voice output)
  4. Speech-to-Text (voice input)
  5. SSL certificates (for browser mic access)
  6. Remote machines (optional - for distributed setups)

Let's get started!
```

### 3. Configuration Sections

#### Section 1: Projects Directory

```
Where do your code projects live?

Current/Default: ~/projects

This is the base directory where AgentWire looks for projects.
Session "myapp" will map to ~/projects/myapp/
```

**Ask:** Use default `~/projects` or specify custom path?

**Validate:** Directory exists or offer to create it.

#### Section 2: Agent Command

```
What command should AgentWire use to start Claude Code?

Options:
  1. claude --dangerously-skip-permissions (Recommended - full automation)
  2. claude (Standard - will prompt for permissions)
  3. Custom command (for Aider, Cursor, or other agents)

The --dangerously-skip-permissions flag allows Claude to run without
confirmation prompts. Only use this if you trust the environment.
```

**Ask:** Which option? If custom, prompt for the full command.

#### Section 3: Text-to-Speech (TTS)

```
Text-to-Speech converts agent responses to spoken audio.

Available backends:
  1. Chatterbox (Local, high quality, requires GPU for speed)
  2. ElevenLabs (Cloud API, requires API key)
  3. None (Text only, no voice output)

Which TTS backend?
```

**If Chatterbox:**
- Ask for server URL (default: http://localhost:8100)
- Ask for default voice (default: "default")
- Note: `agentwire tts start` will launch the server

**If ElevenLabs:**
- Prompt for API key (store in config or env var)
- Ask for default voice ID

**If None:**
- Confirm text-only mode

#### Section 4: Speech-to-Text (STT)

```
Speech-to-Text converts your voice to text for sending to agents.

Available backends:
```

**Detect platform and show relevant options:**

| Platform | Options |
|----------|---------|
| macOS | WhisperKit (fast, local), OpenAI API, None |
| Linux/WSL | whisper.cpp, faster-whisper, OpenAI API, None |

**If local backend:**
- Ask for model path or use default
- Offer to download models if not present

**If OpenAI:**
- Note: Requires OPENAI_API_KEY environment variable

**If None:**
- Confirm typing-only mode (no voice input)

#### Section 5: SSL Certificates

```
SSL certificates are required for browser microphone access.
Browsers only allow mic access over HTTPS.

Options:
  1. Generate self-signed certificates (Recommended for local use)
  2. Use existing certificates (specify paths)
  3. Skip (portal won't work with voice input)
```

**If generate:**
- Run certificate generation
- Show paths to created files

**If existing:**
- Prompt for cert and key paths
- Validate files exist

#### Section 6: Remote Machines (Optional)

```
Do you want to configure remote machines?

Remote machines allow you to run Claude Code sessions on other computers
(e.g., a GPU server for ML work, a cloud devbox, etc.)

Options:
  1. Skip (local only for now)
  2. Add remote machines
```

**If adding machines:**
- For each machine, collect:
  - Machine ID (short name like "gpu-server")
  - Hostname or IP
  - SSH user
  - Projects directory on that machine
- Test SSH connectivity
- Add to machines.json

### 4. Generate Configuration

Create all config files:

**~/.agentwire/config.yaml:**
```yaml
server:
  host: "0.0.0.0"
  port: 8765
  ssl:
    cert: "~/.agentwire/cert.pem"
    key: "~/.agentwire/key.pem"

projects:
  dir: "{user_projects_dir}"
  worktrees:
    enabled: true
    suffix: "-worktrees"

tts:
  backend: "{tts_backend}"
  url: "{tts_url}"
  default_voice: "{tts_voice}"

stt:
  backend: "{stt_backend}"
  language: "en"

agent:
  command: "{agent_command}"
```

**~/.agentwire/machines.json:**
```json
{
  "machines": [
    // user-added machines
  ]
}
```

**~/.agentwire/rooms.json:**
```json
{
  "agentwire": {
    "role": "orchestrator",
    "voice": "{default_voice}"
  }
}
```

**~/.agentwire/roles/:** (create default role files if not exist)

### 5. Summary & Next Steps

```
✓ Configuration complete!

Created:
  ~/.agentwire/config.yaml
  ~/.agentwire/machines.json
  ~/.agentwire/rooms.json
  ~/.agentwire/cert.pem (if generated)
  ~/.agentwire/key.pem (if generated)

Your setup:
  Projects:    ~/projects
  Agent:       claude --dangerously-skip-permissions
  TTS:         Chatterbox @ http://localhost:8100
  STT:         WhisperKit (local)
  Machines:    Local only

Next steps:
  1. agentwire tts start     # Start TTS server (if using Chatterbox)
  2. agentwire portal start  # Start the web portal
  3. Open https://localhost:8765 in your browser

Happy coding! 🎉
```

## Adjustment Mode (when config exists)

When running on existing config, show current values and offer to change each section:

```
Existing AgentWire configuration found.

Current settings:
  Projects:    ~/projects
  Agent:       claude --dangerously-skip-permissions
  TTS:         Chatterbox @ http://localhost:8100
  STT:         WhisperKit
  Machines:    2 configured (devbox-1, gpu-server)

What would you like to do?
  1. Adjust specific settings
  2. Start fresh (backs up current config)
  3. Cancel

If adjusting, which section?
  [P] Projects directory
  [A] Agent command
  [T] TTS settings
  [S] STT settings
  [C] SSL certificates
  [M] Remote machines
  [D] Done - save changes
```

## Error Handling

- If SSH test fails for remote machine: offer to skip or retry
- If certificate generation fails: show error, suggest manual steps
- If directory doesn't exist: offer to create it
- If model download fails: show manual download instructions

## Implementation Notes

The CLI (`agentwire init`) should:
1. Check for existing config
2. Launch interactive prompts using Python's `input()` or a library like `questionary`
3. Validate inputs as they're collected
4. Write all config files atomically (write to temp, then move)
5. Create backup of existing config if starting fresh

For a richer experience, consider using the `questionary` or `rich` libraries for:
- Colored output
- Selection menus
- Progress indicators
- Validation feedback
