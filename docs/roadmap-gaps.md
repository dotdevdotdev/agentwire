# AgentWire Roadmap & Gaps

> Living document. Update this, don't create new versions.

## Built & Working

- Voice interface (push-to-talk, TTS, STT)
- Session management (tmux-based)
- Claude Code + OpenCode support
- Orchestrator/worker pane system
- Remote machine support
- Worktree support for branches
- Damage control hooks
- Portal web UI
- Voice cloning
- Self-hosted TTS (dotdev-pc via SSH tunnel) + RunPod option

## Untested in Real Use

- Hybrid orchestration (Opus orchestrator → GLM workers) on a real project
- Multi-worker coordination across panes
- Worker handoff/status reporting
- GLM-4.7 instruction optimization in practice

## Potentially Missing / Future Ideas

| Feature | Priority | Notes |
|---------|----------|-------|
| Audio streaming | Medium | Currently generates full file before playing |
| Wake word detection | Low | Always PTT currently |
| Session history/replay | Medium | Review past sessions |
| Worker dashboard in portal | Medium | See all panes at once |
| Mobile experience | Low | Portal works but not optimized |
| Integration tests | Medium | Automated testing of workflows |
| Better error recovery | Medium | Worker failures, network issues |

## Validation Needed

The biggest gap is real-world validation of the hybrid orchestration model:

1. Opus 4.5 as voice orchestrator
2. Spawning OpenCode/GLM-4.7 workers for parallel execution
3. Workers reporting back, orchestrator synthesizing results
4. Multi-file changes coordinated across workers

Need to run a real project through this workflow to identify friction points.
