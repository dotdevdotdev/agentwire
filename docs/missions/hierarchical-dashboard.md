# Hierarchical Dashboard Refactor

> Living document. Update this, don't create new versions.

**Status:** Ready for execution
**Branch:** `mission/hierarchical-dashboard`
**Created:** 2026-01-06

## Objective

Transform the dashboard from a flat session list to a hierarchical machine→sessions view that showcases AgentWire's unique multi-machine capability.

## Current State

- Dashboard shows a flat list of all sessions
- Machine information is hidden in session names (e.g., `session@machine`)
- Create session button is top-level
- No clear indication of which sessions are local vs remote
- Multi-machine capability is not visually prominent

## Target State

**Hierarchical View:**
```
▼ Local (3 sessions) [+]
  ├─ ▼ agentwire
  │  ├─ Path: ~/projects/agentwire
  │  ├─ Status: active
  │  ├─ Voice: bashbunni
  │  └─ [Open Room]
  ├─ ▼ api/feature-auth
  │  ├─ Path: ~/projects/api-worktrees/feature-auth
  │  ├─ Branch: feature-auth
  │  ├─ Status: idle
  │  └─ [Open Room]
  └─ ...

▼ dotdev-pc (192.168.1.100) • 2 sessions [+]
  ├─ ▼ ml-training
  │  ├─ Path: ~/projects/ml
  │  ├─ Status: active
  │  └─ [Open Room]
  └─ ...

▶ gpu-server (10.0.0.5) • 0 sessions [+]
```

**Machine Level Info:**
- Status indicator (online/offline)
- Session count
- Host/IP address
- [+] Create session button per machine

**Session Level Info (when expanded):**
- Working directory
- Activity status (idle/active)
- Git branch (if worktree)
- Voice settings
- Open room button

## Architecture

### Data Structure

```javascript
{
  local: {
    id: 'local',
    host: null,
    status: 'online',
    sessions: [...]
  },
  machines: [
    {
      id: 'dotdev-pc',
      host: '192.168.1.100',
      user: 'dotdev',
      projects_dir: '~/projects',
      status: 'online',  // or 'offline'
      sessions: [...]
    }
  ]
}
```

### API Changes

- `/api/sessions` → returns hierarchical data with machine grouping
- `/api/machines` → includes status checks
- `/api/create` → already supports machine parameter

## Waves

### Wave 1: Human Actions (RUNTIME BLOCKING)

None - all changes are self-contained frontend/backend work.

### Wave 2: Backend API Updates

**Task 2.1: Update `/api/sessions` endpoint to return hierarchical data**
- **Files:** `agentwire/server.py`
- **Details:**
  - Modify `handle_sessions` endpoint to group sessions by machine
  - Return structure: `{local: {...}, machines: [{id, host, status, sessions: [...]}]}`
  - Add machine status checks (ping/SSH test)
  - Include session activity status from rooms.json

**Task 2.2: Add `/api/machine/{id}/status` endpoint for real-time status checks**
- **Files:** `agentwire/server.py`
- **Details:**
  - Health check endpoint for individual machines
  - Returns online/offline + session count
  - Used for status indicators in UI

### Wave 3: Frontend Components

**Task 3.1: Create MachineCard component**
- **Files:** `agentwire/static/js/dashboard.js`
- **Details:**
  - Expandable/collapsible machine card
  - Shows: machine name, status indicator, session count, host/IP
  - Per-machine [+] create button
  - Handles local vs remote machines differently (local has no host)

**Task 3.2: Refactor SessionCard to be nested under machines**
- **Files:** `agentwire/static/js/dashboard.js`
- **Details:**
  - Move session card rendering into machine context
  - Expandable to show: path, activity status, branch, voice
  - Update click handler to work within hierarchy

**Task 3.3: Implement expand/collapse state management**
- **Files:** `agentwire/static/js/dashboard.js`
- **Details:**
  - Track expanded state per machine and session
  - Save to localStorage for persistence
  - Default: local expanded, remotes collapsed

### Wave 4: Styling

**Task 4.1: CSS for hierarchical layout**
- **Files:** `agentwire/static/css/dashboard.css`
- **Details:**
  - Indentation for hierarchy levels
  - Expand/collapse icons (▶/▼)
  - Machine card styling with status indicators
  - Session details styling (nested info)

**Task 4.2: Status indicator styles**
- **Files:** `agentwire/static/css/dashboard.css`
- **Details:**
  - Online: green dot
  - Offline: red dot
  - Activity: pulsing animation for active sessions

### Wave 5: Create Session Integration

**Task 5.1: Update create session UI to be per-machine**
- **Files:** `agentwire/static/js/dashboard.js`, `agentwire/templates/dashboard.html`
- **Details:**
  - Remove top-level create session button
  - Add [+] button to each machine card
  - Pre-fill machine field based on which [+] was clicked
  - Show create form as modal or inline expansion

**Task 5.2: Update create session form logic**
- **Files:** `agentwire/static/js/dashboard.js`
- **Details:**
  - Accept machine parameter from clicked [+] button
  - Pre-fill project path with machine's projects_dir
  - Update validation to account for machine-specific paths

### Wave 6: Testing & Polish

**Task 6.1: Add loading states**
- **Files:** `agentwire/static/js/dashboard.js`
- **Details:**
  - Show "Checking status..." for machines
  - Skeleton loaders for session list
  - Error states for offline machines

**Task 6.2: Add empty states**
- **Files:** `agentwire/static/js/dashboard.js`, `agentwire/static/css/dashboard.css`
- **Details:**
  - "No machines configured" → link to add machine
  - "No sessions running" → link to create session
  - Per-machine empty state with helpful text

## Completion Criteria

- [x] Dashboard displays hierarchical machine→sessions view
- [x] Local machine always shown at top
- [x] Remote machines shown with host/IP and status indicator
- [x] Sessions are nested under their respective machines
- [x] Expand/collapse works for machines and sessions
- [x] Create session button is per-machine (removes top-level button)
- [x] Session details show: path, activity, branch (if worktree), voice
- [x] Machine status indicators update in real-time
- [x] State persistence via localStorage (what's expanded/collapsed)
- [x] Empty states for no machines and no sessions
- [x] Mobile responsive (hierarchy collapses gracefully)

## Notes

- This refactor highlights AgentWire's unique selling point: multi-machine orchestration
- The hierarchical view makes it obvious which sessions are local vs remote
- Per-machine create buttons reduce friction for multi-machine workflows
- Status indicators provide immediate feedback on machine availability
