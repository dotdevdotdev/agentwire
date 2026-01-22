# Mission: Agent Parity

## Objective
Ensure agentwire works identically regardless of which agent app (Claude Code or OpenCode) is used for any role. The system should be agent-agnostic.

## Why This Matters
- Flexibility to use any model for any role (Opus for orch, GLM for workers, or vice versa)
- Future-proofing for new agent apps or models
- Consistent behavior = predictable orchestration

## Wave 1: Claude Code Idle Hook Parity

The OpenCode plugin has features the Claude Code hook lacks.

### Current State
| Feature | OpenCode | Claude Code |
|---------|----------|-------------|
| Idle detection | ✓ | ✓ |
| Output capture (last 20 lines) | ✓ | ✗ |
| Auto-kill worker panes | ✓ | ✗ |
| Queue-based notifications | ✓ | ✗ (60s rate limit) |

### Tasks
- [x] Task 1.1: Update `~/.claude/hooks/suppress-bg-notifications.sh` to capture last 20 lines of output before notifying
- [x] Task 1.2: Add auto-kill for worker panes (pane_index > 0) after notification
- [x] Task 1.3: Use queue-based notifications (write to `~/.agentwire/queues/{session}.jsonl`, spawn processor)
- [x] Task 1.4: Test with Claude Code worker panes - verify output captured, pane killed, orchestrator notified

## Wave 2: Verify Core Commands Work for Both

Test these commands work identically for both agent types:

- [ ] Task 2.1: `agentwire spawn` - spawns worker pane with correct agent type
- [ ] Task 2.2: `agentwire send` - sends prompts correctly to both agent types
- [ ] Task 2.3: `agentwire output` - captures output from both agent types
- [ ] Task 2.4: `agentwire kill` - clean shutdown works for both (/exit for Claude Code, appropriate for OpenCode)

## Wave 3: History & Resume

- [ ] Task 3.1: Test `agentwire history list` shows sessions from both agent types
- [ ] Task 3.2: Test `agentwire history resume` works for Claude Code sessions
- [ ] Task 3.3: Test `agentwire history resume` works for OpenCode sessions (if applicable)

## Wave 4: Doctor & Diagnostics

- [ ] Task 4.1: `agentwire doctor` detects missing/broken Claude Code hooks
- [ ] Task 4.2: `agentwire doctor` detects missing/broken OpenCode plugin
- [ ] Task 4.3: `agentwire doctor --yes` auto-fixes both

## Wave 5: Documentation

- [ ] Task 5.1: Update CLAUDE.md with agent-agnostic patterns
- [ ] Task 5.2: Document hook/plugin installation for both agents
- [ ] Task 5.3: Add "Agent Parity" section to architecture docs

## Out of Scope (Later Missions)
- Remote machines
- Voice cloning polish
- Portal UI enhancements
- Worktrees (fork/recreate)

## Success Criteria
1. Can run voice-orchestrator on either Claude Code or OpenCode
2. Can run glm-worker on either Claude Code or OpenCode
3. Idle notifications work identically (output captured, pane killed, queue used)
4. `agentwire doctor` verifies both setups
