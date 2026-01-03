# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Simplified CLI Commands** - Top-level commands with consistent `-s/--session` flag pattern:
  - `agentwire list` (was: `agentwire session list`)
  - `agentwire new -s <name> [-p path] [-f]` (was: `agentwire session new`)
  - `agentwire output -s <session> [-n lines]` (was: `agentwire session output`)
  - `agentwire kill -s <session>` (was: `agentwire session kill`)
  - `agentwire send-keys -s <session> <keys>...` - Send raw keys with pause between groups
  - Legacy `agentwire session *` subcommands still work for backwards compatibility

## [0.1.1] - 2025-01-03

### Added

- **Actions Menu Improvements**
  - Hover popovers showing action names on icon buttons
  - 60x60 circular icon buttons stacked above toggle
  - Smooth fade/slide animations on hover

- **AskUserQuestion TTS**
  - Speaks the question aloud when popup appears
  - Multi-line question support (questions spanning multiple lines)

- **Development Commands**
  - `agentwire rebuild` - Clear uv cache and reinstall from source
  - `agentwire uninstall` - Clean uninstall with cache clearing

### Fixed

- **Fork Session** - Now correctly copies Claude session file to worktree's project directory
  (Claude stores sessions per-project path)
- **Fork Naming** - Changed from `project/fork-timestamp` to `project-fork-N` format
- **AskUserQuestion Parsing** - Fixed regex to match multi-line questions
- **Type Option Detection** - No longer matches "Other players..." as a type-something option
- **Audio Race Condition** - Fixed state reset when new audio interrupts playing audio
- **Terminal Mode Toggle** - Actions button now visible in terminal mode
- **Portal Restart** - Uses tmux directly to avoid attach crash

## [0.1.0] - 2025-01-02

### Added

- **Web Portal** - Multi-room voice interface with push-to-talk and TTS playback
  - Ambient mode with animated orb showing interaction state
  - Terminal mode for direct session interaction
  - Device selectors for microphone and speaker
  - Voice selector per room
  - Image attachments via paste or file picker
  - AskUserQuestion popup modal with clickable options
  - "Type something" option with text input and Send button
  - Actions menu with session management:
    - "New Room" - spawn parallel session in new worktree (opens in new tab)
    - "Fork Session" - fork Claude Code conversation context into new session
    - "Recreate Session" - destroys worktree, pulls latest, fresh start
    - "Restart Service" - for system sessions (agentwire, portal, TTS)
  - Claude Code session ID tracking for fork support
  - System session detection (different actions menu for agentwire services)

- **CLI Commands**
  - `agentwire init` - Interactive setup wizard
  - `agentwire portal start/stop/status` - Manage web portal
  - `agentwire portal start --dev` - Run from source for development
  - `agentwire tts start/stop/status` - Manage TTS server
  - `agentwire say` - Speak text via TTS (local or to room)
  - `agentwire send` - Send prompt to a session
  - `agentwire session list/new/output/kill` - Session management
  - `agentwire machine list/add/remove` - Remote machine management
  - `agentwire skills install/uninstall/status` - Claude Code integration
  - `agentwire voiceclone start/stop/list` - Voice cloning
  - `agentwire generate-certs` - SSL certificate generation
  - `agentwire rebuild` - Clear uv cache and reinstall from source
  - `agentwire uninstall` - Clean uninstall with cache clearing

- **Claude Code Skills** - Session orchestration from within Claude Code
  - `/sessions` - List all tmux sessions
  - `/send` - Send prompt to session
  - `/output` - Read session output
  - `/spawn` - Smart session creation
  - `/new` - Create new session
  - `/kill` - Destroy session
  - `/status` - Check all machines
  - `/jump` - Get attach instructions
  - `/machine-setup` - Add remote machine guide
  - `/machine-remove` - Remove machine guide

- **TTS Backend** - Chatterbox integration with voice cloning support

- **STT Backends** - WhisperKit, whisper.cpp, and OpenAI Whisper API

- **Remote Machine Support** - SSH-based session management on remote servers

- **Git Worktree Support** - Multiple agents working same project in parallel
