# AgentWire CLI Diagram

## Command Overview

```
agentwire
├── Session Commands ─────────────────────────────────────────────────────┐
│   new        Create Claude Code session in tmux                         │
│   send       Send prompt to session (adds Enter)                        │
│   send-keys  Send raw keystrokes to session                             │
│   output     Read session output (capture-pane)                         │
│   kill       Clean shutdown (/exit then kill)                           │
│   list       List sessions (local + all machines)                       │
│   recreate   Destroy session, fresh worktree, restart                   │
│   fork       Clone session with conversation context                    │
│   dev        Start/attach to agentwire orchestrator                     │
│                                                                          │
├── Voice Commands ───────────────────────────────────────────────────────┤
│   say        Speak text (routes to browser or local)                    │
│   listen     Push-to-talk recording                                     │
│   voiceclone Record and upload voice samples                            │
│                                                                          │
├── Infrastructure ───────────────────────────────────────────────────────┤
│   portal     Web server (start/stop/status)                             │
│   tts        TTS server management                                      │
│   tunnels    SSH tunnel management                                      │
│   machine    Remote machine registry                                    │
│   network    Network diagnostics                                        │
│   doctor     Auto-diagnose and fix issues                               │
│                                                                          │
├── Configuration ────────────────────────────────────────────────────────┤
│   init       Interactive setup wizard                                   │
│   template   Session templates (list/show/create)                       │
│   skills     Claude Code skills integration                             │
│   safety     Damage control hooks                                       │
│                                                                          │
└── Development ──────────────────────────────────────────────────────────┤
    rebuild    Clear uv cache, reinstall from source                      │
    uninstall  Remove tool completely                                     │
    generate-certs  Create SSL certificates                               │
──────────────────────────────────────────────────────────────────────────┘
```

## Parameter Reference

### Session Commands

| Command | Parameters |
|---------|-----------|
| `new` | `-s SESSION` (req), `-p PATH`, `-t TEMPLATE`, `-f`, `--no-bypass`, `--restricted`, `--worker`, `--orchestrator`, `--json` |
| `send` | `-s SESSION` (req), `PROMPT`, `--json` |
| `send-keys` | `-s SESSION` (req), `KEYS...` |
| `output` | `-s SESSION` (req), `-n LINES`, `--json` |
| `kill` | `-s SESSION` (req), `--json` |
| `list` | `--local`, `--json` |
| `recreate` | `-s SESSION` (req), `--no-bypass`, `--restricted`, `--json` |
| `fork` | `-s SOURCE` (req), `-t TARGET` (req), `--no-bypass`, `--restricted`, `--json` |
| `dev` | (none) |

### Voice Commands

| Command | Parameters |
|---------|-----------|
| `say` | `TEXT`, `-v VOICE`, `-r ROOM`, `--exaggeration FLOAT`, `--cfg FLOAT` |
| `listen` | `-s SESSION`, `--no-prompt` |
| `listen start` | (none) |
| `listen stop` | `-s SESSION`, `--no-prompt` |
| `listen cancel` | (none) |
| `voiceclone start` | (none) |
| `voiceclone stop` | `NAME` (req) |
| `voiceclone cancel` | (none) |
| `voiceclone list` | (none) |
| `voiceclone delete` | `NAME` (req) |

### Infrastructure Commands

| Command | Parameters |
|---------|-----------|
| `portal start` | `--config PATH`, `--port PORT`, `--host HOST`, `--no-tts`, `--no-stt`, `--dev` |
| `portal serve` | `--config PATH`, `--port PORT`, `--host HOST`, `--no-tts`, `--no-stt` |
| `portal stop` | (none) |
| `portal status` | (none) |
| `tts start` | `--port PORT`, `--host HOST` |
| `tts serve` | `--port PORT`, `--host HOST` |
| `tts stop` | (none) |
| `tts status` | (none) |
| `tunnels up` | (none) |
| `tunnels down` | (none) |
| `tunnels status` | (none) |
| `tunnels check` | (none) |
| `machine list` | (none) |
| `machine add` | `ID` (req), `--host HOST`, `--user USER`, `--projects-dir PATH` |
| `machine remove` | `ID` (req) |
| `network status` | (none) |
| `doctor` | `--dry-run`, `-y/--yes` |

### Configuration Commands

| Command | Parameters |
|---------|-----------|
| `init` | `--quick` |
| `template list` | `--json` |
| `template show` | `NAME` (req), `--json` |
| `template create` | `NAME` (req), `--description`, `--voice`, `--role`, `--project`, `--prompt`, `--no-bypass`, `--restricted`, `-f`, `--json` |
| `template delete` | `NAME` (req), `-f`, `--json` |
| `template install-samples` | `-f`, `--json` |
| `skills install` | `-f`, `--copy` |
| `skills status` | (none) |
| `skills uninstall` | (none) |
| `safety check` | `COMMAND` (req), `-v/--verbose` |
| `safety status` | (none) |
| `safety logs` | `-n/--tail N`, `-s SESSION`, `--today`, `-p PATTERN` |
| `safety install` | (none) |

### Development Commands

| Command | Parameters |
|---------|-----------|
| `rebuild` | (none) |
| `uninstall` | (none) |
| `generate-certs` | (none) |

## Session Commands

### `agentwire new -s <session>`

```
┌─────────────────┐
│  agentwire new  │
│  -s anna        │
│  --orchestrator │
└────────┬────────┘
         │
         │ Parse session name
         │   anna           → local, ~/projects/anna
         │   anna/feature   → local worktree, ~/projects/anna-worktrees/feature
         │   anna@dotdev-pc → remote, SSH to dotdev-pc
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LOCAL                                        │ REMOTE (session@machine) │
├──────────────────────────────────────────────┼──────────────────────────┤
│                                              │                          │
│  1. Check if session exists                  │  1. SSH to machine       │
│     tmux has-session -t anna                 │     ssh user@host        │
│                                              │                          │
│  2. Create directory if needed               │  2. Run same logic       │
│     mkdir -p ~/projects/anna                 │     remotely via SSH     │
│                                              │                          │
│  3. Apply template if -t specified           │                          │
│     Read ~/.agentwire/templates/<name>.yaml  │                          │
│                                              │                          │
│  4. Load role instructions                   │                          │
│     --orchestrator → roles/orchestrator.md   │                          │
│     --worker → roles/worker.md               │                          │
│                                              │                          │
│  5. Create tmux session                      │                          │
│     tmux new-session -d -s anna -c <path>    │                          │
│                                              │                          │
│  6. Start Claude Code                        │                          │
│     tmux send-keys -t anna "claude ..." Enter│                          │
│                                              │                          │
│  7. Set environment                          │                          │
│     AGENTWIRE_ROOM=anna                      │                          │
│     AGENTWIRE_SESSION_TYPE=orchestrator      │                          │
│                                              │                          │
└──────────────────────────────────────────────┴──────────────────────────┘
```

### `agentwire send -s <session> "prompt"`

```
┌──────────────────────┐
│  agentwire send      │
│  -s anna             │
│  "run the tests"     │
└──────────┬───────────┘
           │
           │ Parse session@machine
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ LOCAL                                  │ REMOTE                      │
├────────────────────────────────────────┼─────────────────────────────┤
│                                        │                             │
│  tmux send-keys -t anna                │  ssh user@host \            │
│    "run the tests" Enter               │    "tmux send-keys -t anna  │
│                                        │     'run the tests' Enter"  │
│                                        │                             │
└────────────────────────────────────────┴─────────────────────────────┘
```

### `agentwire output -s <session>`

```
┌──────────────────────┐
│  agentwire output    │
│  -s anna             │
│  -n 50               │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ LOCAL                                  │ REMOTE                      │
├────────────────────────────────────────┼─────────────────────────────┤
│                                        │                             │
│  tmux capture-pane -t anna             │  ssh user@host \            │
│    -p -S -50                           │    "tmux capture-pane ..."  │
│                                        │                             │
│  Returns: last 50 lines of output      │  Returns: remote output     │
│                                        │                             │
└────────────────────────────────────────┴─────────────────────────────┘
```

### `agentwire list`

```
┌──────────────────────┐
│  agentwire list      │
└──────────┬───────────┘
           │
           ├──────────────────────────────────────────┐
           │                                          │
           ▼                                          ▼
┌────────────────────────┐              ┌─────────────────────────────┐
│ LOCAL                  │              │ FOR EACH MACHINE            │
│                        │              │ (from ~/.agentwire/         │
│  tmux list-sessions    │              │       machines.json)        │
│    -F "#{...}"         │              │                             │
│                        │              │  ssh user@host -p port \    │
│  Returns:              │              │    "tmux list-sessions"     │
│    session: windows    │              │                             │
│    anna: 1             │              │  Returns:                   │
│    api/feature: 1      │              │    ml: 1                    │
│                        │              │    training: 1              │
└────────────────────────┘              └─────────────────────────────┘
           │                                          │
           └──────────────┬───────────────────────────┘
                          ▼
                   Combined output:
                   LOCAL:
                     anna: 1 window
                   dotdev-pc:
                     ml: 1 window
```

### `agentwire kill -s <session>`

```
┌──────────────────────┐
│  agentwire kill      │
│  -s anna/feature     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  1. Send /exit to Claude Code (clean shutdown)                       │
│     tmux send-keys -t anna/feature "/exit" Enter                     │
│                                                                      │
│  2. Wait for Claude to exit gracefully                               │
│     sleep 2                                                          │
│                                                                      │
│  3. Kill tmux session                                                │
│     tmux kill-session -t anna/feature                                │
│                                                                      │
│  4. If worktree session (name contains /):                           │
│     cd ~/projects/anna                                               │
│     git worktree remove anna-worktrees/feature                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Voice Commands

### `agentwire say "text"`

```
┌───────────────────────────────┐
│  agentwire say "Hello world"  │
│                               │
│  Options:                     │
│    -v, --voice NAME           │
│    -r, --room NAME            │
│    --exaggeration FLOAT (0-1) │
│    --cfg FLOAT (0-1)          │
└──────────────┬────────────────┘
               │
               │ Determine room:
           │   1. -r flag
           │   2. AGENTWIRE_ROOM env
           │   3. .agentwire.yml in cwd
           │   4. Path inference (~/projects/anna → anna)
           │   5. tmux session name
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Check portal for browser connections                                │
│                                                                      │
│  GET https://localhost:8765/api/rooms/{room}/connections             │
│  Try variants: anna, anna@Jordans-Mini, anna@local                   │
│                                                                      │
└──────────────────────┬──────────────────────────────┬────────────────┘
                       │                              │
            has_connections: true          has_connections: false
                       │                              │
                       ▼                              ▼
┌──────────────────────────────────┐   ┌──────────────────────────────┐
│  BROWSER PLAYBACK                │   │  LOCAL PLAYBACK              │
│                                  │   │                              │
│  POST /api/say/{room}            │   │  POST /api/local-tts/{room}  │
│  Body: { "text": "Hello world" } │   │  Body: { "text": "...",      │
│                                  │   │          "voice": "..." }    │
│  Portal:                         │   │                              │
│    → Calls RunPod TTS            │   │  Portal:                     │
│    → Streams audio to browser    │   │    → Calls RunPod TTS        │
│    → Browser plays audio         │   │    → Plays on server speaker │
│                                  │   │                              │
└──────────────────────────────────┘   └──────────────────────────────┘
```

### `agentwire listen`

```
┌──────────────────────┐
│  agentwire listen    │
│  start               │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Start audio recording                                               │
│  (uses system microphone via sounddevice)                            │
│                                                                      │
│  Saves to: /tmp/agentwire_recording.wav                              │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│  agentwire listen    │
│  stop -s anna        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  1. Stop recording                                                   │
│                                                                      │
│  2. Send audio to STT                                                │
│     POST http://stt:8100/transcribe                                  │
│     Body: multipart audio file                                       │
│     Response: { "text": "transcribed text" }                         │
│                                                                      │
│  3. Send to session                                                  │
│     tmux send-keys -t anna "[Voice] transcribed text" Enter          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Infrastructure Commands

### `agentwire portal start`

```
┌───────────────────────────────┐
│  agentwire portal start       │
│                               │
│  Options:                     │
│    --config PATH              │
│    --port PORT (default 8765) │
│    --host HOST (default 0.0.0.0)
│    --no-tts                   │
│    --no-stt                   │
│    --dev (run from source)    │
└──────────────┬────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  1. Create tmux session                                              │
│     tmux new-session -d -s agentwire-portal                          │
│                                                                      │
│  2. Start FastAPI server                                             │
│     --dev: tmux send-keys "uv run agentwire portal serve" Enter      │
│     else:  tmux send-keys "agentwire portal serve" Enter             │
│                                                                      │
│  Portal serves:                                                      │
│     https://localhost:8765        Web UI                             │
│     wss://localhost:8765/ws/...   WebSocket for voice                │
│     /api/say/{room}               TTS to browser                     │
│     /api/local-tts/{room}         TTS to local speaker               │
│     /api/rooms/{room}/connections Connection status                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### `agentwire machine list`

```
┌──────────────────────┐
│  agentwire machine   │
│  list                │
└──────────┬───────────┘
           │
           │ Read ~/.agentwire/machines.json
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  For each machine:                                                   │
│                                                                      │
│  1. Test SSH connectivity                                            │
│     ssh -o ConnectTimeout=5 user@host "echo ok"                      │
│                                                                      │
│  2. Count tmux sessions                                              │
│     ssh user@host "tmux list-sessions | wc -l"                       │
│                                                                      │
│  Output:                                                             │
│    dotdev-pc    online   2 sessions                                  │
│    gpu-server   offline  -                                           │
│    portal       online   1 session                                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Configuration Commands

### `agentwire safety check "command"`

```
┌──────────────────────┐
│  agentwire safety    │
│  check "rm -rf /"    │
└──────────┬───────────┘
           │
           │ Load patterns from
           │ ~/.agentwire/hooks/damage-control/
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  1. Load blocked patterns                                            │
│     patterns/blocked.txt                                             │
│       rm -rf *                                                       │
│       git push --force                                               │
│       *.drop                                                         │
│                                                                      │
│  2. Load allowed patterns                                            │
│     patterns/allowed.txt                                             │
│       npm run *                                                      │
│       pytest *                                                       │
│                                                                      │
│  3. Match command against patterns                                   │
│     "rm -rf /" matches "rm -rf *"                                    │
│                                                                      │
│  Output:                                                             │
│    BLOCKED: matches pattern "rm -rf *"                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Config Files

```
~/.agentwire/
├── config.yaml          # Main config
│   ├── tts.backend      # runpod | chatterbox
│   ├── tts.runpod_*     # RunPod credentials
│   ├── stt.backend      # remote | local
│   └── stt.url          # STT endpoint
│
├── machines.json        # Remote machine registry
│   └── machines[]
│       ├── id           # dotdev-pc
│       ├── host         # hostname or IP
│       ├── port         # SSH port (default 22)
│       ├── user         # SSH user
│       └── projects_dir # ~/projects
│
├── rooms.json           # Per-room settings
│   └── rooms{}
│       ├── voice        # Default voice
│       └── permissions  # Access control
│
├── roles/               # Role instructions
│   ├── orchestrator.md  # Voice-first coordinator
│   ├── worker.md        # Autonomous executor
│   └── chatbot.md       # Conversational agent
│
├── templates/           # Session templates
│   └── <name>.yaml
│       ├── description
│       ├── role
│       └── initial_prompt
│
└── hooks/               # Claude Code hooks
    └── damage-control/
        ├── bash-tool-damage-control.py
        └── patterns/
            ├── blocked.txt
            └── allowed.txt
```

## Session Name Resolution

```
Input                    Machine      Path                                    Branch
─────────────────────────────────────────────────────────────────────────────────────
anna                     local        ~/projects/anna                         -
anna/feature             local        ~/projects/anna-worktrees/feature       feature
anna@dotdev-pc           dotdev-pc    ~/projects/anna (remote)                -
anna/feature@dotdev-pc   dotdev-pc    ~/projects/anna-worktrees/feature       feature
```
