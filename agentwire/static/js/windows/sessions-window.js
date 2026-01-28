/**
 * Sessions Window - displays all sessions with status and action buttons
 */

import { ListWindow } from '../list-window.js';
import { desktop } from '../desktop-manager.js';
import { sessionIcons } from '../icon-manager.js';
import { IconPicker } from '../components/icon-picker.js';
import { ListCard, getActivityIndicatorHtml } from '../components/list-card.js';

/** @type {IconPicker|null} */
let iconPicker = null;

/**
 * Get icon URL for a session by name (uses IconManager for persistence)
 * Use this for terminal/chat windows where icon should be consistent for a session name.
 * @param {string} sessionName - Session name
 * @returns {Promise<string>} Icon URL
 */
export async function getSessionIconByName(sessionName) {
    return sessionIcons.getIcon(sessionName);
}

/** @type {ListWindow|null} */
let sessionsWindow = null;

/** @type {Function|null} */
let unsubscribe = null;

/** @type {Function|null} - Activity event unsubscribe */
let unsubscribeActivity = null;

/** @type {Function|null} - TTS start event unsubscribe */
let unsubscribeTtsStart = null;

/** @type {Function|null} - Audio event unsubscribe */
let unsubscribeAudio = null;

/** @type {Function|null} - Audio ended event unsubscribe */
let unsubscribeAudioEnded = null;

/** @type {Map<string, string>} - Activity state per session */
const sessionActivityStates = new Map();

/** @type {Map<string, number>} - Activity timeout per session */
const sessionActivityTimeouts = new Map();

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
        if (unsubscribeActivity) {
            unsubscribeActivity();
            unsubscribeActivity = null;
        }
        if (unsubscribeTtsStart) {
            unsubscribeTtsStart();
            unsubscribeTtsStart = null;
        }
        if (unsubscribeAudio) {
            unsubscribeAudio();
            unsubscribeAudio = null;
        }
        if (unsubscribeAudioEnded) {
            unsubscribeAudioEnded();
            unsubscribeAudioEnded = null;
        }
        // Clear activity tracking
        sessionActivityStates.clear();
        sessionActivityTimeouts.forEach(t => clearTimeout(t));
        sessionActivityTimeouts.clear();
        sessionsWindow = null;
    };

    // Auto-refresh when sessions change via WebSocket
    unsubscribe = desktop.on('sessions', () => {
        sessionsWindow?.refresh();
    });

    // Subscribe to activity events
    unsubscribeActivity = desktop.on('session_activity', ({ session, active }) => {
        updateSessionActivityIndicator(session, active ? 'processing' : 'idle');
    });

    unsubscribeTtsStart = desktop.on('tts_start', ({ session }) => {
        updateSessionActivityIndicator(session, 'generating');
    });

    unsubscribeAudio = desktop.on('audio', ({ session }) => {
        updateSessionActivityIndicator(session, 'playing');
    });

    unsubscribeAudioEnded = desktop.on('audio_ended', ({ session }) => {
        // Return to idle (or processing if recently active)
        const currentState = sessionActivityStates.get(session);
        if (currentState === 'generating' || currentState === 'playing') {
            updateSessionActivityIndicator(session, 'idle');
        }
    });

    sessionsWindow.open();
    return sessionsWindow;
}

/**
 * Fetch all sessions (local and remote) from API endpoints
 * @returns {Promise<Array>} Array of session objects
 */
async function fetchSessions() {
    // Fetch local and remote sessions in parallel
    const [localResponse, remoteResponse] = await Promise.all([
        fetch('/api/sessions/local'),
        fetch('/api/sessions/remote')
    ]);

    const localData = await localResponse.json();
    const remoteData = await remoteResponse.json();

    // Get local sessions
    const localSessions = (localData.sessions || []).map(s => ({
        ...s,
        machine: null
    }));

    // Get remote sessions from all machines
    const remoteSessions = [];
    for (const machine of (remoteData.machines || [])) {
        for (const s of (machine.sessions || [])) {
            remoteSessions.push({
                ...s,
                machine: machine.id
            });
        }
    }

    // Combine and sort alphabetically
    const allSessions = [...localSessions, ...remoteSessions].sort((a, b) =>
        a.name.localeCompare(b.name)
    );

    // Get session names and assign icons (uses IconManager with persistence)
    const sessionNames = allSessions.map(s => s.name);
    const iconUrls = await sessionIcons.getIconsForItems(sessionNames);

    return allSessions.map((s) => ({
        name: s.name,
        active: s.activity === 'active',
        type: s.type || 'bare',
        path: s.path || null,
        machine: s.machine || null,
        // Chat button shown for agent session types (not bare)
        hasVoice: s.type && (s.type.startsWith('claude-') || s.type.startsWith('opencode-')),
        // Attached client count for presence indicator
        clientCount: s.client_count || 0,
        // Icon URL from IconManager (persistent, name-matched or random)
        iconUrl: iconUrls[s.name]
    }));
}

/**
 * Render a single session item as a card with icon
 * @param {Object} session - Session data
 * @returns {string} HTML string for the session item
 */
function renderSessionItem(session) {
    // Get stored activity state or default to session's initial state
    const activityState = sessionActivityStates.get(session.name) || (session.active ? 'processing' : 'idle');

    // Format path for display
    const pathDisplay = formatPath(session.path);

    // Build meta info line with spans
    const metaParts = [];
    if (session.machine) {
        metaParts.push(`<span class="session-machine">@${session.machine}</span>`);
    }
    if (session.type && session.type !== 'bare') {
        metaParts.push(`<span class="session-type">${session.type}</span>`);
    }
    if (pathDisplay) {
        metaParts.push(`<span class="session-path">${pathDisplay}</span>`);
    }

    // Build actions array
    const actions = [
        { label: 'Monitor', action: 'monitor' }
    ];
    if (session.hasVoice) {
        actions.push({ label: 'Chat', action: 'chat' });
    }
    actions.push({ label: 'Connect', action: 'connect', primary: true });
    actions.push({ label: '✕', action: 'close', danger: true, title: 'Close session' });

    return ListCard({
        id: session.name,
        iconUrl: session.iconUrl,
        activityState: activityState,
        name: session.name,
        clientCount: session.clientCount,
        meta: metaParts.join(' · '),
        actions
    });
}

/**
 * Update activity indicator for a session in the list
 * @param {string} session - Session name
 * @param {string} state - New activity state
 */
function updateSessionActivityIndicator(session, state) {
    // Don't downgrade from TTS states unless explicitly going to idle
    const currentState = sessionActivityStates.get(session);
    if ((currentState === 'generating' || currentState === 'playing') && state === 'processing') {
        return;
    }

    // Store the state
    sessionActivityStates.set(session, state);

    // Find and update the indicator in the DOM
    const indicator = document.querySelector(`.session-activity-indicator[data-session="${session}"]`);
    if (indicator) {
        indicator.classList.remove('idle', 'processing', 'generating', 'playing');
        indicator.classList.add(state);
        indicator.innerHTML = getActivityIndicatorHtml(state);
    }
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
 * @param {string} action - The action type ('monitor', 'connect', 'chat', 'edit-icon')
 * @param {Object} item - The session data object
 */
function handleSessionAction(action, item) {
    if (action === 'monitor') {
        openSessionTerminal(item.name, 'monitor', item.machine);
    } else if (action === 'connect') {
        openSessionTerminal(item.name, 'terminal', item.machine);
    } else if (action === 'chat') {
        openSessionChat(item.name);
    } else if (action === 'close') {
        closeSession(item.name);
    } else if (action === 'edit-icon') {
        openIconPicker(item.name);
    }
}

/**
 * Open the icon picker for a session
 * @param {string} sessionName - Session name
 */
function openIconPicker(sessionName) {
    if (!iconPicker) {
        iconPicker = new IconPicker(sessionIcons);
    }
    iconPicker.show(sessionName, () => {
        // Refresh the list after icon change
        sessionsWindow?.refresh();
    });
}

/**
 * Open a session in terminal or monitor mode
 * Uses the exported function from desktop.js for proper taskbar integration
 * @param {string} session - Session name
 * @param {string} mode - 'monitor' or 'terminal'
 * @param {string|null} machine - Remote machine ID (optional)
 */
function openSessionTerminal(session, mode, machine = null) {
    import('../desktop.js').then(({ openSessionTerminal: openTerminal }) => {
        openTerminal(session, mode, machine);
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
