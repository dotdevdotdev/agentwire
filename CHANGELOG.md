# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-02

### Added

- **Web Portal** - Multi-room voice interface with push-to-talk and TTS playback
  - Ambient mode with animated orb showing interaction state
  - Terminal mode for direct session interaction
  - Device selectors for microphone and speaker
  - Voice selector per room
  - Image attachments via paste or file picker

- **CLI Commands**
  - `agentwire init` - Interactive setup wizard
  - `agentwire portal start/stop/status` - Manage web portal
  - `agentwire tts start/stop/status` - Manage TTS server
  - `agentwire say` - Speak text via TTS (local or to room)
  - `agentwire send` - Send prompt to a session
  - `agentwire session list/new/output/kill` - Session management
  - `agentwire machine list/add/remove` - Remote machine management
  - `agentwire skills install/uninstall/status` - Claude Code integration
  - `agentwire voiceclone start/stop/list` - Voice cloning
  - `agentwire generate-certs` - SSL certificate generation

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
