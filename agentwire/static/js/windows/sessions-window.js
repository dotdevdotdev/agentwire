/**
 * Sessions Window - displays all sessions with status and action buttons
 */

import { ListWindow } from '../list-window.js';
import { desktop } from '../desktop-manager.js';

/**
 * Open the Sessions window
 * @returns {ListWindow} The sessions window instance
 */
export function openSessionsWindow() {
    const win = new ListWindow({
        id: 'sessions',
        title: 'Sessions',
        fetchData: fetchSessions,
        renderItem: renderSessionItem,
        onItemAction: handleSessionAction,
        refreshInterval: 5000
    });

    win.open();
    return win;
}

/**
 * Fetch sessions from API
 * API returns {machines: [{id, sessions: [...]}]} - flatten to get all sessions
 * @returns {Promise<Array>} Array of session objects
 */
async function fetchSessions() {
    const response = await fetch('/api/sessions');
    const data = await response.json();

    const sessions = [];
    for (const machine of (data.machines || [])) {
        for (const session of (machine.sessions || [])) {
            sessions.push({
                name: session.name,
                active: session.status === 'active',
                machine: machine.id !== 'local' ? machine.id : null
            });
        }
    }
    return sessions;
}

/**
 * Render a single session item
 * @param {Object} session - Session data
 * @returns {string} HTML string for the session item
 */
function renderSessionItem(session) {
    const statusClass = session.active ? 'active' : 'idle';
    const statusText = session.active ? '● Active' : '○ Idle';
    const machineTag = session.machine
        ? `<span class="session-machine">@${session.machine}</span>`
        : '';

    return `
        <div class="list-item" data-session="${session.name}">
            <div class="session-info">
                <span class="session-name">${session.name}</span>
                <span class="session-status ${statusClass}">${statusText}</span>
                ${machineTag}
            </div>
            <div class="list-item-actions">
                <button class="btn btn-monitor" data-action="monitor">Monitor</button>
                <button class="btn btn-connect" data-action="connect">Connect</button>
            </div>
        </div>
    `;
}

/**
 * Handle action button clicks on session items
 * @param {string} action - The action type ('monitor' or 'connect')
 * @param {HTMLElement} item - The list item element
 */
function handleSessionAction(action, item) {
    const session = item.dataset.session;
    if (action === 'monitor') {
        openSessionTerminal(session, 'monitor');
    } else if (action === 'connect') {
        openSessionTerminal(session, 'terminal');
    }
}

/**
 * Open a session in terminal or monitor mode
 * @param {string} session - Session name
 * @param {string} mode - 'monitor' or 'terminal'
 */
function openSessionTerminal(session, mode) {
    import('../session-window.js').then(({ SessionWindow }) => {
        const sw = new SessionWindow({ session, mode });
        sw.open();
    });
}
