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
import { openProjectsWindow } from './windows/projects-window.js';

// State - track open SessionWindows
const sessionWindows = new Map();  // sessionId -> SessionWindow instance
let windowCounter = 0;  // For cascading positions

// Global PTT state
let globalPttState = 'idle';  // idle | recording | processing
let globalMediaRecorder = null;
let globalAudioChunks = [];

// DOM Elements (simplified - only what we need)
const elements = {
    desktopArea: document.getElementById('desktopArea'),
    taskbarWindows: document.getElementById('taskbarWindows'),
    menuTime: document.getElementById('menuTime'),
    connectionStatus: document.getElementById('connectionStatus'),
    sessionCount: document.getElementById('sessionCount'),
    globalPtt: document.getElementById('globalPtt'),
};

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupClock();
    setupMenuListeners();
    setupPageUnload();
    setupGlobalPtt();

    // Set up event listeners BEFORE fetching data
    desktop.on('sessions', updateSessionCount);
    desktop.on('disconnect', () => updateConnectionStatus(false));
    desktop.on('connect', () => updateConnectionStatus(true));

    // Handle tmux hook notifications
    desktop.on('session_closed', handleSessionClosed);
    desktop.on('session_created', handleSessionCreated);
    desktop.on('pane_died', handlePaneDied);
    desktop.on('session_renamed', handleSessionRenamed);
    desktop.on('window_activity', handleWindowActivity);

    await desktop.connect();
    updateConnectionStatus(true);

    // Fetch initial data (will emit events to listeners above)
    await desktop.fetchSessions();
}

/**
 * Handle session_closed event from tmux hook.
 * Closes the session window if open and refreshes the sessions list.
 */
function handleSessionClosed({ session }) {
    console.log('[Desktop] Session closed:', session);

    // Close the session window if it's open
    if (sessionWindows.has(session)) {
        const sw = sessionWindows.get(session);
        sw.close();
        sessionWindows.delete(session);
        removeTaskbarButton(session);
    }

    // Sessions list will be updated by the sessions_update event
    // that the portal sends along with session_closed
}

/**
 * Handle session_created event from tmux hook.
 * Sessions list will be updated automatically via sessions_update.
 */
function handleSessionCreated({ session }) {
    console.log('[Desktop] Session created:', session);
    // Sessions list will be updated by the sessions_update event
}

/**
 * Handle pane_died event from tmux hook.
 * Refreshes session info to update pane counts.
 */
function handlePaneDied({ session, pane_id }) {
    console.log('[Desktop] Pane died:', session, pane_id);
    // Sessions list (with pane counts) will be updated by sessions_update event
}

/**
 * Handle session_renamed event from tmux hook.
 * Updates open windows and taskbar buttons with new session name.
 */
function handleSessionRenamed({ old_name, new_name }) {
    console.log('[Desktop] Session renamed:', old_name, '->', new_name);

    // Update session window if open
    if (old_name && sessionWindows.has(old_name)) {
        const sw = sessionWindows.get(old_name);
        sessionWindows.delete(old_name);
        sessionWindows.set(new_name, sw);

        // Update taskbar button
        removeTaskbarButton(old_name);
        addTaskbarButton(new_name, sw);
    }

    // Sessions list will be updated by sessions_update event
}

/**
 * Handle window_activity event from tmux hook.
 * Shows desktop notification for background session activity.
 */
function handleWindowActivity({ session }) {
    console.log('[Desktop] Window activity:', session);

    // Only notify if session window is not focused
    if (desktop.getActiveWindow() !== session) {
        // Request notification permission if needed
        if (Notification.permission === 'granted') {
            new Notification(`Activity in ${session}`, {
                body: 'Session has new output',
                icon: '/static/img/icon-192.png',
                tag: `activity-${session}`,  // Prevent duplicate notifications
            });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }
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
    // Left side menu items
    document.getElementById('projectsMenu')?.addEventListener('click', () => {
        openProjectsWindow();
    });
    document.getElementById('sessionsMenu')?.addEventListener('click', () => {
        openSessionsWindow();
    });

    // Right side settings dropdown items
    document.getElementById('machinesMenuItem')?.addEventListener('click', () => {
        openMachinesWindow();
        closeSettingsDropdown();
    });
    document.getElementById('configMenuItem')?.addEventListener('click', () => {
        openConfigWindow();
        closeSettingsDropdown();
    });

    // Settings dropdown toggle (click to open/close)
    const settingsMenu = document.getElementById('settingsMenu');
    settingsMenu?.addEventListener('click', (e) => {
        // Don't toggle if clicking on dropdown items
        if (e.target.closest('.dropdown-item')) return;
        settingsMenu.classList.toggle('active');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#settingsMenu')) {
            closeSettingsDropdown();
        }
    });
}

function closeSettingsDropdown() {
    document.getElementById('settingsMenu')?.classList.remove('active');
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
    elements.sessionCount.innerHTML = `<span class="count">${count}</span><span class="count-label"> session${count !== 1 ? 's' : ''}</span>`;
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
            desktop.setActiveWindow(id);
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

// Global PTT - always sends to "agentwire" session
function setupGlobalPtt() {
    const btn = elements.globalPtt;
    if (!btn) return;

    // Mouse events
    btn.addEventListener('mousedown', startGlobalRecording);
    btn.addEventListener('mouseup', stopGlobalRecording);
    btn.addEventListener('mouseleave', stopGlobalRecording);

    // Touch events for mobile
    btn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startGlobalRecording();
    });
    btn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopGlobalRecording();
    });

    // Global keyboard shortcut (Ctrl/Cmd + Space)
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.code === 'Space' && globalPttState === 'idle') {
            e.preventDefault();
            startGlobalRecording();
        }
    });
    document.addEventListener('keyup', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.code === 'Space' && globalPttState === 'recording') {
            e.preventDefault();
            stopGlobalRecording();
        }
    });
}

async function startGlobalRecording() {
    if (globalPttState !== 'idle') return;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        globalMediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });

        globalAudioChunks = [];
        globalMediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) globalAudioChunks.push(e.data);
        };

        globalMediaRecorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            if (globalAudioChunks.length > 0) {
                await processGlobalRecording();
            }
        };

        globalMediaRecorder.start();
        updateGlobalPttState('recording');
    } catch (err) {
        console.error('[GlobalPTT] Failed to start recording:', err);
    }
}

function stopGlobalRecording() {
    if (globalPttState !== 'recording' || !globalMediaRecorder) return;
    globalMediaRecorder.stop();
    updateGlobalPttState('processing');
}

async function processGlobalRecording() {
    try {
        const blob = new Blob(globalAudioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', blob, 'recording.webm');

        // Transcribe
        const transcribeRes = await fetch('/transcribe', {
            method: 'POST',
            body: formData
        });
        const { text } = await transcribeRes.json();

        if (text && text.trim()) {
            // Send to agentwire session with voice prompt
            await fetch('/send/agentwire', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: `[Voice input - respond with say command] ${text}`
                })
            });
            console.log('[GlobalPTT] Sent to agentwire:', text);
        }
    } catch (err) {
        console.error('[GlobalPTT] Processing failed:', err);
    } finally {
        updateGlobalPttState('idle');
    }
}

function updateGlobalPttState(state) {
    globalPttState = state;
    const btn = elements.globalPtt;
    if (!btn) return;

    btn.classList.remove('recording', 'processing');
    const icon = btn.querySelector('.ptt-icon');

    switch (state) {
        case 'recording':
            btn.classList.add('recording');
            if (icon) icon.textContent = '🔴';
            break;
        case 'processing':
            btn.classList.add('processing');
            if (icon) icon.textContent = '⏳';
            break;
        default:
            if (icon) icon.textContent = '🎤';
    }
}
