# Expand/Collapse State Management Usage

## Overview

The expand/collapse state management system provides persistent UI state for the hierarchical dashboard. State is stored in localStorage and survives page reloads.

## API Reference

### Storage Key

```javascript
const STORAGE_KEY_EXPAND_STATE = 'agentwire:dashboard:expandedState';
```

### Data Structure

```javascript
{
  machines: {
    'local': true,           // Local machine expanded by default
    'gpu-server': false,     // Remote machines collapsed by default
    'dotdev-pc': true        // User expanded this remote
  },
  sessions: {
    'my-session': true,      // User expanded this session
    'api/feature': false     // Collapsed session
  }
}
```

### Functions

#### `getExpandedState(): Object`

Retrieves current expand/collapse state from localStorage.

**Returns:** State object with `machines` and `sessions` keys.

**Default behavior:**
- If no state exists, returns default: local expanded, all remotes collapsed
- If localStorage data is corrupt, returns default state
- Sessions default to collapsed

```javascript
const state = getExpandedState();
console.log(state.machines.local);  // true (local expanded by default)
console.log(state.machines['gpu-server']);  // undefined (not yet set)
```

#### `setExpandedState(state: Object): void`

Saves expand/collapse state to localStorage.

**Parameters:**
- `state` - State object with `machines` and `sessions`

```javascript
const state = getExpandedState();
state.machines['new-machine'] = true;
setExpandedState(state);
```

#### `isMachineExpanded(machineId: string): boolean`

Checks if a machine is currently expanded.

**Parameters:**
- `machineId` - Machine ID (e.g., 'local', 'gpu-server')

**Returns:** `true` if expanded, `false` if collapsed

**Default behavior:**
- Returns `true` for 'local' if not explicitly set
- Returns `false` for remote machines if not explicitly set

```javascript
if (isMachineExpanded('local')) {
  // Render expanded machine card
}
```

#### `toggleMachineExpanded(machineId: string): boolean`

Toggles a machine's expand/collapse state.

**Parameters:**
- `machineId` - Machine ID

**Returns:** New state (`true` = expanded, `false` = collapsed)

**Side effects:** Saves to localStorage

```javascript
const newState = toggleMachineExpanded('gpu-server');
console.log(newState);  // true (now expanded)
```

#### `isSessionExpanded(sessionName: string): boolean`

Checks if a session is currently expanded (showing details).

**Parameters:**
- `sessionName` - Session name

**Returns:** `true` if expanded, `false` if collapsed

**Default behavior:** Sessions default to `false` (collapsed)

```javascript
if (isSessionExpanded('my-session')) {
  // Render expanded session details (path, branch, voice, etc.)
}
```

#### `toggleSessionExpanded(sessionName: string): boolean`

Toggles a session's expand/collapse state.

**Parameters:**
- `sessionName` - Session name

**Returns:** New state (`true` = expanded, `false` = collapsed)

**Side effects:** Saves to localStorage

```javascript
const newState = toggleSessionExpanded('my-session');
console.log(newState);  // true (now expanded)
```

#### `cleanupExpandedState(machines: Array, sessions: Array): void`

Removes state for machines/sessions that no longer exist.

**Parameters:**
- `machines` - Array of machine objects with `id` field
- `sessions` - Array of session objects with `name` field

**Side effects:**
- Removes entries from state that aren't in the provided arrays
- Saves to localStorage if any changes were made
- Always preserves 'local' machine entry

**Usage:** Call this when loading fresh data to prevent stale state from deleted items.

```javascript
cleanupExpandedState(
  [{ id: 'gpu-server' }, { id: 'dotdev-pc' }],
  [{ name: 'session1' }, { name: 'session2' }]
);
```

## Integration Examples

### MachineCard Component (Wave 3.1)

```javascript
function renderMachineCard(machine) {
  const isExpanded = isMachineExpanded(machine.id);

  const card = document.createElement('div');
  card.className = 'machine-card';

  // Header with expand/collapse icon
  const header = document.createElement('div');
  header.className = 'machine-header';
  header.innerHTML = `
    <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
    <span class="machine-name">${machine.id}</span>
    <span class="session-count">${machine.sessions.length} sessions</span>
  `;

  // Toggle expand on click
  header.addEventListener('click', () => {
    const newState = toggleMachineExpanded(machine.id);
    renderDashboard();  // Re-render to show/hide sessions
  });

  card.appendChild(header);

  // Sessions list (only if expanded)
  if (isExpanded) {
    const sessionsList = document.createElement('div');
    sessionsList.className = 'sessions-list';
    machine.sessions.forEach(session => {
      sessionsList.appendChild(renderSessionCard(session));
    });
    card.appendChild(sessionsList);
  }

  return card;
}
```

### SessionCard Component (Wave 3.2)

```javascript
function renderSessionCard(session) {
  const isExpanded = isSessionExpanded(session.name);

  const card = document.createElement('div');
  card.className = 'session-card';

  // Header with session name
  const header = document.createElement('div');
  header.className = 'session-header';
  header.innerHTML = `
    <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
    <span class="session-name">${session.name}</span>
    <span class="activity-indicator ${session.activity}"></span>
  `;

  // Toggle expand on click
  header.addEventListener('click', () => {
    const newState = toggleSessionExpanded(session.name);
    renderDashboard();  // Re-render to show/hide details
  });

  card.appendChild(header);

  // Details (only if expanded)
  if (isExpanded) {
    const details = document.createElement('div');
    details.className = 'session-details';
    details.innerHTML = `
      <div>Path: ${session.path}</div>
      <div>Voice: ${session.voice}</div>
      ${session.branch ? `<div>Branch: ${session.branch}</div>` : ''}
      <button onclick="openRoom('${session.name}')">Open Room</button>
    `;
    card.appendChild(details);
  }

  return card;
}
```

### Loading Data with Cleanup

```javascript
async function loadDashboard() {
  const [machines, sessions] = await Promise.all([
    fetch('/api/machines').then(r => r.json()),
    fetch('/api/sessions').then(r => r.json())
  ]);

  // Clean up stale state before rendering
  cleanupExpandedState(machines, sessions);

  renderDashboard(machines, sessions);
}
```

## Testing

A test file is available at `test_expand_state.html` which includes:
- Unit tests for all functions
- Edge case testing
- localStorage persistence verification
- State cleanup validation

Open the file in a browser to run the tests.

## Notes

- State persists across page reloads via localStorage
- Default state: local expanded, remotes collapsed, all sessions collapsed
- Cleanup should be called when loading fresh data to prevent stale entries
- All functions handle missing/corrupt localStorage gracefully
- localStorage key uses namespaced format: `agentwire:dashboard:expandedState`
