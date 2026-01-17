# Mission: Portal Pane Support

> Optional enhancements for pane-based workers visibility in the web portal.

## Context

Pane-based workers (mission/pane-based-workers) are now implemented. Workers spawn as tmux panes within the orchestrator's session, creating a visual dashboard in the terminal.

**Current state**: The portal works correctly with pane-based workers:
- Voice/text input goes to orchestrator (pane 0) ✅
- Output capture shows orchestrator output ✅
- Workers are managed via CLI commands by the orchestrator ✅

**Gap**: The portal has no visibility into worker panes. Users can only see workers in the terminal, not the web interface.

## Problem

When workers are running:
- Dashboard shows "1 session" but doesn't indicate 3 workers are active
- Session page monitor mode only shows pane 0 (orchestrator)
- No way to view individual worker output from the portal
- No way to kill a stuck worker without using CLI

## Solution

Add pane awareness to the portal for improved visibility and control.

### Priority 1: Dashboard Pane Count

Show pane count on session cards when workers are active:
- "agentwire session • 3 panes" instead of just "agentwire session"
- Only show when panes > 1 (workers exist)

### Priority 2: Session Page Pane Selector

Add pane dropdown in monitor mode:
- Default: "Pane 0 (Orchestrator)"
- Workers: "Pane 1 (Worker)", "Pane 2 (Worker)", etc.
- Switching panes changes the output stream

### Priority 3: Worker Management UI

Session page additions:
- "Workers" section showing active panes with status
- Kill button per worker pane
- Optional: "Spawn Worker" button (convenience alternative to voice)

## Wave 1: Human Actions (RUNTIME BLOCKING)

- [ ] None required

## Wave 2: Backend - Pane Listing API

Add pane info to existing APIs:

- [ ] Update `/api/sessions` to include `pane_count` per session
  - Use `pane_manager.list_panes()` for local sessions
  - Use SSH `tmux list-panes` for remote sessions

- [ ] Add `/api/session/{name}/panes` endpoint
  - Returns list of panes: `[{index, command, active}]`
  - Works for local and remote sessions

## Wave 3: Backend - Pane Output API

- [ ] Update `get_output()` in `agents/tmux.py` to accept optional `pane` parameter
  - Default: pane 0 (orchestrator)
  - When specified: capture specific pane output

- [ ] Update `/ws/{name}` WebSocket to support pane switching
  - Add `{"type": "switch_pane", "pane": 1}` message type
  - Output stream switches to specified pane

## Wave 4: Backend - Pane Control API

- [ ] Add `/api/session/{name}/panes/{index}/kill` endpoint
  - Uses `pane_manager.kill_pane()`
  - Refuses to kill pane 0

- [ ] Add `/api/session/{name}/panes/spawn` endpoint
  - Uses `pane_manager.spawn_worker_pane()`
  - Returns new pane index

## Wave 5: Dashboard UI

- [ ] Update `renderSessionCard()` in `dashboard.js`
  - Show pane count badge when `pane_count > 1`
  - Style: subtle indicator like "(3 panes)" or worker icon

## Wave 6: Session Page - Monitor Mode

- [ ] Add pane selector dropdown above output area
  - Populated from `/api/session/{name}/panes`
  - Default: Pane 0
  - Changing selection sends WebSocket `switch_pane` message

- [ ] Update output display to show which pane is active
  - Label: "Output: Pane 0 (Orchestrator)" or "Output: Pane 2 (Worker)"

## Wave 7: Session Page - Worker Management

- [ ] Add "Workers" section (collapsible, below voice controls)
  - List format: "Pane 1: claude • Pane 2: claude"
  - Kill button per pane
  - Auto-refresh every 5s when expanded

- [ ] Optional: "Spawn Worker" button
  - Calls `/api/session/{name}/panes/spawn`
  - Updates worker list

## Completion Criteria

- [ ] Dashboard shows pane count for sessions with workers
- [ ] Monitor mode can view any pane's output
- [ ] Can kill individual worker panes from session page
- [ ] Pane count updates in real-time (via existing activity WebSocket)

## Notes

- Pane index 0 is always the orchestrator (protected from kill)
- Workers (panes 1+) are created/managed by orchestrator
- This mission is optional - pane-based workers work without portal support
- Focus on visibility first, control features are lower priority

## Dependencies

- Requires pane-based workers mission complete ✅
- Uses existing `pane_manager.py` module

## References

- Pane manager: `agentwire/pane_manager.py`
- Mission: `docs/missions/pane-based-workers.md`
- Portal server: `agentwire/server.py`
- Dashboard JS: `agentwire/static/js/dashboard.js`
- Session JS: `agentwire/static/js/session.js`
