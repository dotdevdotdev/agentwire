# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-18

Initial public release of AgentWire.

### Added

- **Desktop Control Center** - WinBox-powered window management with draggable/resizable session windows
- **Session Windows** - Monitor mode (read-only output) or Terminal mode (full xterm.js) per session
- **Push-to-Talk Voice** - Hold to speak, release to send transcription from any device
- **TTS Playback** - Agent responses spoken back via browser audio with smart routing
- **Multi-Device Access** - Control sessions from phone, tablet, or laptop on your network
- **Git Worktrees** - Multiple agents work the same project in parallel on separate branches
- **Remote Machines** - Orchestrate Claude Code sessions on remote servers via SSH
- **Safety Hooks** - 300+ dangerous command patterns blocked (rm -rf, git push --force, secret exposure)
- **Session Roles** - Orchestrator sessions coordinate voice, workers execute focused tasks
- **Permission Hooks** - Claude Code integration for permission dialogs in the portal

### CLI Commands

- `agentwire init` - Interactive setup wizard
- `agentwire portal start/stop/status` - Portal management
- `agentwire tts start/stop/status` - TTS server management
- `agentwire stt start/stop/status` - STT server management
- `agentwire new/list/kill/send/output` - Session management
- `agentwire spawn/split/detach/jump` - Pane management
- `agentwire say` - TTS with smart audio routing
- `agentwire safety check/status/logs` - Security diagnostics
- `agentwire machine add/remove/list` - Remote machine management
- `agentwire tunnels up/down/status` - SSH tunnel management
- `agentwire history list/show/resume` - Session history
- `agentwire doctor` - Auto-diagnose and fix issues
- `agentwire generate-certs` - SSL certificate generation

### Security

- Damage control hooks protecting against 300+ dangerous command patterns
- Zero-access paths for credentials, SSH keys, and API tokens
- Read-only paths for system configs
- No-delete paths for session and mission files
- Audit logging for all security decisions

### Documentation

- Comprehensive README with platform-specific installation instructions
- Architecture documentation
- Troubleshooting guide
- TTS setup guide
- Remote machines guide
- Security documentation

[0.1.0]: https://github.com/dotdevdotdev/agentwire/releases/tag/v0.1.0
