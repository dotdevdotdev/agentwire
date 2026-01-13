/**
 * Desktop UI - OS-like window manager for AgentWire
 */

// State
const state = {
    sessions: [],
    machines: [],
    windows: new Map(), // sessionName -> WinBox instance
    activeWindow: null,
    ws: null,
};

// DOM Elements
const elements = {
    sessionsList: document.getElementById('sessionsList'),
    machinesList: document.getElementById('machinesList'),
    sessionCount: document.getElementById('sessionCount'),
    connectionStatus: document.getElementById('connectionStatus'),
    desktopArea: document.getElementById('desktopArea'),
    taskbarWindows: document.getElementById('taskbarWindows'),
    menuTime: document.getElementById('menuTime'),
    welcomeMessage: document.getElementById('welcomeMessage'),
    newSessionModal: document.getElementById('newSessionModal'),
    voiceIndicator: document.getElementById('voiceIndicator'),
};

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupClock();
    setupEventListeners();
    await loadSessions();
    await loadMachines();
    connectWebSocket();
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

// Event Listeners
function setupEventListeners() {
    // New session button
    document.getElementById('newSessionBtn').addEventListener('click', () => {
        elements.newSessionModal.classList.add('active');
    });

    // Modal close
    document.getElementById('closeNewSessionModal').addEventListener('click', () => {
        elements.newSessionModal.classList.remove('active');
    });

    document.getElementById('cancelNewSession').addEventListener('click', () => {
        elements.newSessionModal.classList.remove('active');
    });

    // Create session
    document.getElementById('createNewSession').addEventListener('click', createSession);

    // Close modal on backdrop click
    elements.newSessionModal.addEventListener('click', (e) => {
        if (e.target === elements.newSessionModal) {
            elements.newSessionModal.classList.remove('active');
        }
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('active'));
        }
    });
}

// Load sessions
async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        const data = await response.json();
        // API returns {machines: [{sessions: [...]}]} - flatten to get all sessions
        const allSessions = [];
        for (const machine of (data.machines || [])) {
            for (const session of (machine.sessions || [])) {
                allSessions.push(session);
            }
        }
        state.sessions = allSessions;
        renderSessionsList();
        updateSessionCount();
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

// Load machines
async function loadMachines() {
    try {
        const response = await fetch('/api/machines');
        const data = await response.json();
        // API returns array directly, not {machines: [...]}
        state.machines = Array.isArray(data) ? data : (data.machines || []);
        renderMachinesList();
        populateMachineSelect();
    } catch (error) {
        console.error('Failed to load machines:', error);
    }
}

// Render sessions list in dropdown
function renderSessionsList() {
    if (state.sessions.length === 0) {
        elements.sessionsList.innerHTML = '<div class="loading">No active sessions</div>';
        return;
    }

    elements.sessionsList.innerHTML = state.sessions.map(session => `
        <div class="session-item" data-session="${session.name}">
            <div>
                <div class="session-name">${session.name}</div>
                <div class="session-status ${session.status === 'active' ? 'active' : ''}">${session.status}</div>
            </div>
        </div>
    `).join('');

    // Add click handlers
    elements.sessionsList.querySelectorAll('.session-item').forEach(item => {
        item.addEventListener('click', () => {
            const name = item.dataset.session;
            openSessionWindow(name);
        });
    });
}

// Render machines list
function renderMachinesList() {
    if (state.machines.length === 0) {
        elements.machinesList.innerHTML = '<div class="loading">No machines configured</div>';
        return;
    }

    elements.machinesList.innerHTML = state.machines.map(machine => `
        <div class="machine-item" data-machine="${machine.id}">
            <span>${machine.id}</span>
            <span class="status-dot ${machine.status === 'online' ? 'connected' : ''}"></span>
        </div>
    `).join('');
}

// Populate machine select in new session modal
function populateMachineSelect() {
    const select = document.getElementById('newSessionMachine');
    select.innerHTML = '<option value="">Local</option>' +
        state.machines.map(m => `<option value="${m.id}">${m.id}</option>`).join('');
}

// Update session count
function updateSessionCount() {
    const count = state.sessions.length;
    elements.sessionCount.innerHTML = `<span class="count">${count}</span> session${count !== 1 ? 's' : ''}`;
}

// Open session window
function openSessionWindow(sessionName) {
    // Check if window already exists
    if (state.windows.has(sessionName)) {
        const win = state.windows.get(sessionName);
        win.focus();
        return;
    }

    // Hide welcome message
    elements.welcomeMessage.style.display = 'none';

    // Create window content
    const content = document.createElement('div');
    content.className = 'session-window';
    content.innerHTML = `
        <div class="session-terminal" id="terminal-${sessionName}"></div>
        <div class="session-toolbar">
            <button class="session-voice-btn" id="voice-${sessionName}">
                🎤 Hold to Talk
            </button>
            <div class="session-status-bar">
                Connected to ${sessionName}
            </div>
        </div>
    `;

    // Calculate position (cascade windows)
    const offset = state.windows.size * 30;
    const x = 50 + offset;
    const y = 50 + offset;

    // Create WinBox window
    const win = new WinBox({
        title: sessionName,
        mount: content,
        root: elements.desktopArea,
        x: x,
        y: y,
        width: 700,
        height: 500,
        minwidth: 400,
        minheight: 300,
        onclose: () => {
            state.windows.delete(sessionName);
            removeTaskbarButton(sessionName);
            if (state.windows.size === 0) {
                elements.welcomeMessage.style.display = 'block';
            }
            // Clean up terminal
            if (win.terminal) {
                win.terminal.dispose();
            }
            if (win.ws) {
                win.ws.close();
            }
        },
        onfocus: () => {
            state.activeWindow = sessionName;
            updateTaskbarActive(sessionName);
        },
        onminimize: () => {
            updateTaskbarButton(sessionName, true);
        },
        onrestore: () => {
            updateTaskbarButton(sessionName, false);
        }
    });

    state.windows.set(sessionName, win);
    addTaskbarButton(sessionName, win);

    // Initialize terminal
    initTerminal(sessionName, win);
}

// Initialize terminal in window
function initTerminal(sessionName, win) {
    const terminalEl = document.getElementById(`terminal-${sessionName}`);
    if (!terminalEl || typeof Terminal === 'undefined') return;

    const terminal = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        theme: {
            background: '#0d1117',
            foreground: '#e6edf3',
            cursor: '#2ea043',
            selection: 'rgba(46, 160, 67, 0.3)',
        }
    });

    const fitAddon = new FitAddon.FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(terminalEl);
    fitAddon.fit();

    win.terminal = terminal;
    win.fitAddon = fitAddon;

    // Handle window resize
    const resizeObserver = new ResizeObserver(() => {
        fitAddon.fit();
    });
    resizeObserver.observe(terminalEl);

    // Connect to terminal WebSocket
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/terminal/${sessionName}`);

    ws.onopen = () => {
        terminal.write('\x1b[32m● Connected to session\x1b[0m\r\n\r\n');
    };

    ws.onmessage = (event) => {
        // Handle binary data (terminal output)
        if (event.data instanceof Blob) {
            event.data.text().then(text => terminal.write(text));
        } else if (event.data instanceof ArrayBuffer) {
            terminal.write(new TextDecoder().decode(event.data));
        } else {
            terminal.write(event.data);
        }
    };

    ws.onclose = () => {
        terminal.write('\r\n\x1b[31m● Disconnected\x1b[0m\r\n');
    };

    // Send input as JSON
    terminal.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'input', data }));
        }
    });

    win.ws = ws;
}

// Taskbar management
function addTaskbarButton(sessionName, win) {
    const btn = document.createElement('div');
    btn.className = 'taskbar-btn active';
    btn.dataset.session = sessionName;
    btn.innerHTML = `<span>📟</span> ${sessionName}`;
    btn.addEventListener('click', () => {
        if (win.min) {
            win.restore();
        } else {
            win.focus();
        }
    });
    elements.taskbarWindows.appendChild(btn);
}

function removeTaskbarButton(sessionName) {
    const btn = elements.taskbarWindows.querySelector(`[data-session="${sessionName}"]`);
    if (btn) btn.remove();
}

function updateTaskbarActive(sessionName) {
    elements.taskbarWindows.querySelectorAll('.taskbar-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.session === sessionName);
    });
}

function updateTaskbarButton(sessionName, minimized) {
    const btn = elements.taskbarWindows.querySelector(`[data-session="${sessionName}"]`);
    if (btn) {
        btn.classList.toggle('minimized', minimized);
    }
}

// Create new session
async function createSession() {
    const name = document.getElementById('newSessionName').value.trim();
    const machine = document.getElementById('newSessionMachine').value;
    const path = document.getElementById('newSessionPath').value.trim();
    const voice = document.getElementById('newSessionVoice').value;
    const errorEl = document.getElementById('newSessionError');

    if (!name) {
        errorEl.textContent = 'Session name is required';
        return;
    }

    errorEl.textContent = '';

    const sessionName = machine ? `${name}@${machine}` : name;

    try {
        const response = await fetch('/api/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session: sessionName,
                path: path || undefined,
                voice: voice,
                type: 'claude-bypass',
            })
        });

        if (!response.ok) {
            const data = await response.json();
            errorEl.textContent = data.error || 'Failed to create session';
            return;
        }

        elements.newSessionModal.classList.remove('active');
        document.getElementById('newSessionName').value = '';
        document.getElementById('newSessionPath').value = '';

        // Reload sessions and open the new one
        await loadSessions();
        openSessionWindow(sessionName);

    } catch (error) {
        errorEl.textContent = 'Failed to create session';
        console.error(error);
    }
}

// WebSocket for real-time updates
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';

    // We'll use a general status endpoint or poll for now
    // The main WS connections are per-session

    // Update connection status
    elements.connectionStatus.innerHTML = `
        <span class="status-dot connected"></span>
        <span class="status-text">Connected</span>
    `;

    // Poll for session updates every 10s
    setInterval(async () => {
        await loadSessions();
    }, 10000);
}
