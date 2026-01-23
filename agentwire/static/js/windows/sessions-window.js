/**
 * Sessions Window - displays all sessions with status and action buttons
 */

import { ListWindow } from '../list-window.js';
import { desktop } from '../desktop-manager.js';

/** Session icon filenames (12 icons, wraps for more sessions) */
const SESSION_ICONS = [
    'agentwire.png',
    'android.png',
    'cat.png',
    'crown.png',
    'cyborg.png',
    'drone.png',
    'fox.png',
    'mech.png',
    'microphone.png',
    'owl.png',
    'robot.png',
    'wolf.png'
];

/**
 * Get icon for a session by index (wraps around if more sessions than icons)
 * @param {number} index - Session index in the list
 * @returns {string} Icon URL
 */
function getSessionIconUrl(index) {
    const iconFile = SESSION_ICONS[index % SESSION_ICONS.length];
    return `/static/icons/sessions/${iconFile}`;
}

/** @type {ListWindow|null} */
let sessionsWindow = null;

/** @type {Function|null} */
let unsubscribe = null;

/**
 * Open the Sessions window
 * @returns {ListWindow} The sessions window instance
 */
export function openSessionsWindow() {
    if (sessionsWindow?.winbox) {
        sessionsWindow.winbox.focus();
        return sessionsWindow;
    }

    sessionsWindow = new ListWindow({
        id: 'sessions',
        title: 'Sessions',
        fetchData: fetchSessions,
        renderItem: renderSessionItem,
        onItemAction: handleSessionAction,
        emptyMessage: 'No sessions'
    });

    sessionsWindow._cleanup = () => {
        if (unsubscribe) {
            unsubscribe();
            unsubscribe = null;
        }
        sessionsWindow = null;
    };

    // Auto-refresh when sessions change via WebSocket
    unsubscribe = desktop.on('sessions', () => {
        sessionsWindow?.refresh();
    });

    sessionsWindow.open();
    return sessionsWindow;
}

/**
 * Fetch local sessions from fast API endpoint
 * @returns {Promise<Array>} Array of session objects
 */
async function fetchSessions() {
    const response = await fetch('/api/sessions/local');
    const data = await response.json();
    return (data.sessions || []).map((s, index) => ({
        name: s.name,
        active: s.activity === 'active',
        type: s.type || 'bare',
        path: s.path || null,
        // Chat button shown for agent session types (not bare)
        hasVoice: s.type && (s.type.startsWith('claude-') || s.type.startsWith('opencode-')),
        // Attached client count for presence indicator
        clientCount: s.client_count || 0,
        // Icon URL based on position in list (alphabetically ordered)
        iconUrl: getSessionIconUrl(index)
    }));
}

/**
 * Render a single session item as a card with icon
 * @param {Object} session - Session data
 * @returns {string} HTML string for the session item
 */
function renderSessionItem(session) {
    const statusClass = session.active ? 'active' : 'idle';
    const chatButton = session.hasVoice
        ? '<button class="btn btn-small" data-action="chat">Chat</button>'
        : '';

    // Presence indicator - user icon with count badge
    const presenceIndicator = session.clientCount > 0
        ? `<span class="presence-indicator" title="${session.clientCount} client${session.clientCount !== 1 ? 's' : ''} attached">
             <span class="presence-icon">👤</span>
             <span class="presence-count">${session.clientCount}</span>
           </span>`
        : '';

    // Format path for display (show last 2 segments or full if short)
    const pathDisplay = formatPath(session.path);

    // Use pre-assigned icon URL based on list position
    const iconUrl = session.iconUrl;

    // Build meta info line
    const metaParts = [];
    if (session.type && session.type !== 'bare') {
        metaParts.push(`<span class="session-type">${session.type}</span>`);
    }
    if (pathDisplay) {
        metaParts.push(`<span class="session-path">${pathDisplay}</span>`);
    }
    const metaLine = metaParts.length > 0
        ? `<div class="session-meta">${metaParts.join(' · ')}</div>`
        : '';

    return `
        <div class="session-card ${statusClass}">
            <div class="session-icon-wrapper">
                <img src="${iconUrl}" alt="" class="session-icon" />
                <span class="session-status-dot ${statusClass}"></span>
            </div>
            <div class="session-content">
                <div class="session-header">
                    <span class="session-name" data-session="${session.name}">${session.name}</span>
                    ${presenceIndicator}
                </div>
                ${metaLine}
            </div>
            <div class="session-actions">
                <button class="btn btn-small" data-action="monitor">Monitor</button>
                ${chatButton}
                <button class="btn btn-small btn-primary" data-action="connect">Connect</button>
                <button class="btn btn-small danger" data-action="close" title="Close session">✕</button>
            </div>
        </div>
    `;
}

/**
 * Format path for display - show abbreviated version
 * @param {string|null} path - Full path
 * @returns {string} Formatted path
 */
function formatPath(path) {
    if (!path) return '';

    // Replace home directory with ~ (detect common patterns)
    // Matches: /Users/username, /home/username, /root
    const homeMatch = path.match(/^(\/Users\/[^/]+|\/home\/[^/]+|\/root)/);
    if (homeMatch) {
        return '~' + path.slice(homeMatch[1].length);
    }

    return path;
}

/**
 * Handle action button clicks on session items
 * @param {string} action - The action type ('monitor', 'connect', or 'chat')
 * @param {Object} item - The session data object
 */
function handleSessionAction(action, item) {
    if (action === 'monitor') {
        openSessionTerminal(item.name, 'monitor');
    } else if (action === 'connect') {
        openSessionTerminal(item.name, 'terminal');
    } else if (action === 'chat') {
        openSessionChat(item.name);
    } else if (action === 'close') {
        closeSession(item.name);
    }
}

/**
 * Open a session in terminal or monitor mode
 * Uses the exported function from desktop.js for proper taskbar integration
 * @param {string} session - Session name
 * @param {string} mode - 'monitor' or 'terminal'
 */
function openSessionTerminal(session, mode) {
    import('../desktop.js').then(({ openSessionTerminal: openTerminal }) => {
        openTerminal(session, mode);
    });
}

/**
 * Open a chat window connected to a session
 * @param {string} session - Session name
 */
function openSessionChat(session) {
    import('./chat-window.js').then(({ openChatWindow }) => {
        openChatWindow(session);
    });
}

/**
 * Close/kill a session
 * @param {string} session - Session name
 */
async function closeSession(session) {
    if (!confirm(`Close session "${session}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/sessions/${encodeURIComponent(session)}`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (data.error) {
            console.error('[SessionsWindow] Failed to close session:', data.error);
            alert(`Failed to close session: ${data.error}`);
        }
        // Session list will auto-refresh via WebSocket event
    } catch (err) {
        console.error('[SessionsWindow] Failed to close session:', err);
        alert(`Failed to close session: ${err.message}`);
    }
}
