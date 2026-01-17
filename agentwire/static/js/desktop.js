/**
 * Desktop UI - OS-like window manager for AgentWire
 *
 * Refactored to use modular architecture:
 * - DesktopManager for WebSocket and state
 * - SessionWindow for terminal windows
 * - List windows for sessions/machines/config
 */

import { desktop } from './desktop-manager.js';
import { SessionWindow } from './session-window.js';
import { openSessionsWindow } from './windows/sessions-window.js';
import { openMachinesWindow } from './windows/machines-window.js';
import { openConfigWindow } from './windows/config-window.js';

// State - track open SessionWindows
const sessionWindows = new Map();  // sessionId -> SessionWindow instance
let windowCounter = 0;  // For cascading positions

// DOM Elements (simplified - only what we need)
const elements = {
    desktopArea: document.getElementById('desktopArea'),
    taskbarWindows: document.getElementById('taskbarWindows'),
    menuTime: document.getElementById('menuTime'),
    connectionStatus: document.getElementById('connectionStatus'),
    sessionCount: document.getElementById('sessionCount'),
};

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupClock();
    setupMenuListeners();
    setupPageUnload();

    // Set up event listeners BEFORE fetching data
    desktop.on('sessions', updateSessionCount);
    desktop.on('disconnect', () => updateConnectionStatus(false));
    desktop.on('connect', () => updateConnectionStatus(true));

    await desktop.connect();
    updateConnectionStatus(true);

    // Fetch initial data (will emit events to listeners above)
    await desktop.fetchSessions();
}

// Clean up on page unload
function setupPageUnload() {
    window.addEventListener('beforeunload', () => {
        // Disconnect main WebSocket
        desktop.disconnect();

        // Close all session windows (which closes their WebSockets)
        sessionWindows.forEach(sw => sw.close());
    });
}

// Menu listeners - open windows when menu items clicked
function setupMenuListeners() {
    document.getElementById('sessionsMenu')?.addEventListener('click', () => {
        openSessionsWindow();
    });
    document.getElementById('machinesMenu')?.addEventListener('click', () => {
        openMachinesWindow();
    });
    document.getElementById('configMenu')?.addEventListener('click', () => {
        openConfigWindow();
    });
}

// Clock
function setupClock() {
    function updateTime() {
        const now = new Date();
        elements.menuTime.textContent = now.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    updateTime();
    setInterval(updateTime, 1000);
}

// Connection status
function updateConnectionStatus(connected) {
    elements.connectionStatus.innerHTML = connected
        ? '<span class="status-dot connected"></span><span class="status-text">Connected</span>'
        : '<span class="status-dot disconnected"></span><span class="status-text">Disconnected</span>';
}

// Session count
function updateSessionCount(sessions) {
    const count = sessions?.length || 0;
    elements.sessionCount.innerHTML = `<span class="count">${count}</span> session${count !== 1 ? 's' : ''}`;
}

/**
 * Open a session terminal window.
 * Exported for use by sessions-window.js and other modules.
 *
 * @param {string} session - Session name
 * @param {'monitor'|'terminal'} mode - Window mode
 * @param {string|null} machine - Remote machine ID (optional)
 */
export function openSessionTerminal(session, mode, machine = null) {
    const id = machine ? `${session}@${machine}` : session;

    // Check if already open
    if (sessionWindows.has(id)) {
        sessionWindows.get(id).focus();
        return;
    }

    // Calculate cascade position
    const offset = (windowCounter++ % 10) * 30;

    const sw = new SessionWindow({
        session,
        mode,
        machine,
        root: elements.desktopArea,
        position: { x: 50 + offset, y: 50 + offset },
        onClose: (win) => {
            sessionWindows.delete(id);
            removeTaskbarButton(id);
        },
        onFocus: (win) => {
            updateTaskbarActive(id);
        }
    });

    sw.open();
    sessionWindows.set(id, sw);
    addTaskbarButton(id, sw);
}

// Taskbar management
function addTaskbarButton(id, sessionWindow) {
    const btn = document.createElement('div');
    btn.className = 'taskbar-btn active';
    btn.dataset.session = id;
    btn.innerHTML = `<span>📟</span> ${id}`;
    btn.addEventListener('click', () => {
        if (sessionWindow.isMinimized) {
            sessionWindow.restore();
        } else {
            sessionWindow.focus();
        }
    });
    elements.taskbarWindows.appendChild(btn);
}

function removeTaskbarButton(id) {
    const btn = elements.taskbarWindows.querySelector(`[data-session="${id}"]`);
    if (btn) btn.remove();
}

function updateTaskbarActive(id) {
    elements.taskbarWindows.querySelectorAll('.taskbar-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.session === id);
    });
}
