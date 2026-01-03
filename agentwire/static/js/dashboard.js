/**
 * Dashboard JS - AgentWire Dashboard Page
 * ES Module for dashboard functionality
 */

// Get default voice from the page (set by Jinja2)
const DEFAULT_VOICE = window.AGENTWIRE_CONFIG?.defaultVoice || 'bashbunni';

// =============================================================================
// Accordion Toggle
// =============================================================================

function toggleAction(id) {
    const group = document.getElementById(id);
    if (group) {
        group.classList.toggle('open');
    }
}

// =============================================================================
// Permission Mode Selection
// =============================================================================

function selectPermissionMode(element, bypass) {
    // Remove selected class from all options
    document.querySelectorAll('.radio-option').forEach(opt => opt.classList.remove('selected'));
    // Add selected class to clicked option
    element.classList.add('selected');
    // Check the radio button
    const radio = element.querySelector('input[type="radio"]');
    if (radio) {
        radio.checked = true;
    }
}

// =============================================================================
// Sessions
// =============================================================================

async function loadSessions() {
    const res = await fetch('/api/sessions');
    const sessions = await res.json();
    const container = document.getElementById('sessions');
    const sessionCountEl = document.getElementById('sessionCount');

    if (sessions.length === 0) {
        container.innerHTML = '<div class="no-sessions">No active sessions. Create one to get started.</div>';
        if (sessionCountEl) {
            sessionCountEl.innerHTML = '<span class="count">0</span> active sessions';
        }
        return;
    }

    // Update session count in left column
    if (sessionCountEl) {
        sessionCountEl.innerHTML =
            `<span class="count">${sessions.length}</span> active session${sessions.length !== 1 ? 's' : ''}`;
    }

    container.innerHTML = sessions.map(s => {
        const bypassBadge = s.bypass_permissions !== false
            ? '<span class="session-badge bypass">Bypass</span>'
            : '<span class="session-badge prompted">Prompted</span>';
        return `
        <div class="session-card">
            <a href="/room/${s.name}" style="flex:1;text-decoration:none;color:inherit;">
                <div class="session-name">${s.name}${s.machine ? '<span style="color:var(--text-muted);font-weight:normal">@' + s.machine + '</span>' : ''}${bypassBadge}</div>
                <div class="session-meta">
                    ${s.path || '~/projects/' + s.name}
                    <span class="session-voice">• ${s.voice || DEFAULT_VOICE}</span>
                </div>
            </a>
            <button class="session-close" data-session="${s.name}" title="Close session">✕</button>
        </div>
    `}).join('');

    // Attach close handlers
    container.querySelectorAll('.session-close').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            closeSession(btn.dataset.session);
        });
    });
}

async function createSession() {
    const nameInput = document.getElementById('sessionName');
    const pathInput = document.getElementById('projectPath');
    const voiceSelect = document.getElementById('sessionVoice');
    const bypassRadio = document.querySelector('input[name="bypassPermissions"]:checked');
    const errorEl = document.getElementById('error');

    const name = nameInput?.value.trim() || '';
    const path = pathInput?.value.trim() || '';
    const voice = voiceSelect?.value || DEFAULT_VOICE;
    const bypassPermissions = bypassRadio?.value === 'true';

    if (!name) {
        if (errorEl) errorEl.textContent = 'Session name is required';
        return;
    }

    if (errorEl) errorEl.textContent = '';

    const res = await fetch('/api/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, path: path || null, voice, bypass_permissions: bypassPermissions })
    });

    const data = await res.json();
    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        window.location.href = '/room/' + name;
    }
}

async function closeSession(name) {
    if (!confirm(`Close session "${name}"?`)) return;

    const res = await fetch(`/api/sessions/${encodeURIComponent(name)}`, {
        method: 'DELETE'
    });
    const data = await res.json();

    if (data.error) {
        alert('Failed to close session: ' + data.error);
    } else {
        loadSessions();
        loadArchive();
    }
}

// =============================================================================
// Machines
// =============================================================================

async function loadMachines() {
    const res = await fetch('/api/machines');
    const machines = await res.json();
    const container = document.getElementById('machinesList');

    if (!container) return;

    if (machines.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;margin-bottom:0.5rem;">No machines available</div>';
        return;
    }

    container.innerHTML = machines.map(m => `
        <div class="machine-item">
            <div>
                <span class="status-dot ${m.status}"></span>
                <span class="machine-id">${m.id}</span>
                ${m.local ? '<span class="machine-local">(this machine)</span>' : ''}
            </div>
            <div>
                <span class="machine-host">${m.local ? '' : (m.user ? m.user + '@' : '') + m.host}</span>
                ${!m.local ? `<button class="machine-remove" data-machine="${m.id}" title="Remove machine">✕</button>` : ''}
            </div>
        </div>
    `).join('');

    // Attach remove handlers
    container.querySelectorAll('.machine-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            removeMachine(btn.dataset.machine);
        });
    });
}

async function addMachine() {
    const idInput = document.getElementById('machineId');
    const hostInput = document.getElementById('machineHost');
    const userInput = document.getElementById('machineUser');
    const projectsDirInput = document.getElementById('machineProjectsDir');
    const errorEl = document.getElementById('machineError');

    const id = idInput?.value.trim() || '';
    const host = hostInput?.value.trim() || '';
    const user = userInput?.value.trim() || '';
    const projectsDir = projectsDirInput?.value.trim() || '';

    if (!id || !host) {
        if (errorEl) errorEl.textContent = 'ID and host are required';
        return;
    }

    if (errorEl) errorEl.textContent = '';

    const res = await fetch('/api/machines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            id,
            host,
            user: user || null,
            projects_dir: projectsDir || null
        })
    });

    const data = await res.json();
    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        if (idInput) idInput.value = '';
        if (hostInput) hostInput.value = '';
        if (userInput) userInput.value = '';
        if (projectsDirInput) projectsDirInput.value = '';
        loadMachines();
    }
}

async function removeMachine(id) {
    if (!confirm(`Remove machine "${id}" from AgentWire?\n\nThis only removes it from the portal. The remote machine itself is not affected.`)) return;

    const res = await fetch(`/api/machines/${encodeURIComponent(id)}`, {
        method: 'DELETE'
    });
    const data = await res.json();

    if (data.error) {
        alert('Failed to remove machine: ' + data.error);
    } else {
        loadMachines();
        if (data.rooms_removed && data.rooms_removed.length > 0) {
            console.log('Removed room configs:', data.rooms_removed);
        }
    }
}

// =============================================================================
// Config Editor
// =============================================================================

async function loadConfig() {
    const res = await fetch('/api/config');
    const data = await res.json();

    const pathText = data.path + (data.exists ? '' : ' (new file)');
    const configPathEl = document.getElementById('configPath');
    const modalConfigPathEl = document.getElementById('modalConfigPath');
    const configEditorEl = document.getElementById('configEditor');
    const modalConfigEditorEl = document.getElementById('modalConfigEditor');

    if (configPathEl) configPathEl.textContent = pathText;
    if (modalConfigPathEl) modalConfigPathEl.textContent = pathText;
    if (configEditorEl) configEditorEl.value = data.content;
    if (modalConfigEditorEl) modalConfigEditorEl.value = data.content;
}

function openConfigModal() {
    const configEditorEl = document.getElementById('configEditor');
    const modalConfigEditorEl = document.getElementById('modalConfigEditor');
    const modalConfigSuccessEl = document.getElementById('modalConfigSuccess');
    const modalConfigErrorEl = document.getElementById('modalConfigError');
    const modalEl = document.getElementById('configModal');

    // Sync content from inline editor to modal
    if (modalConfigEditorEl && configEditorEl) {
        modalConfigEditorEl.value = configEditorEl.value;
    }
    if (modalConfigSuccessEl) modalConfigSuccessEl.textContent = '';
    if (modalConfigErrorEl) modalConfigErrorEl.textContent = '';
    if (modalEl) modalEl.classList.add('open');
    if (modalConfigEditorEl) modalConfigEditorEl.focus();
}

function closeConfigModal() {
    const configEditorEl = document.getElementById('configEditor');
    const modalConfigEditorEl = document.getElementById('modalConfigEditor');
    const modalEl = document.getElementById('configModal');

    // Sync content from modal back to inline editor
    if (configEditorEl && modalConfigEditorEl) {
        configEditorEl.value = modalConfigEditorEl.value;
    }
    if (modalEl) modalEl.classList.remove('open');
}

async function saveConfigModal() {
    const errorEl = document.getElementById('modalConfigError');
    const successEl = document.getElementById('modalConfigSuccess');
    const modalConfigEditorEl = document.getElementById('modalConfigEditor');
    const configEditorEl = document.getElementById('configEditor');

    const content = modalConfigEditorEl?.value || '';
    if (errorEl) errorEl.textContent = '';
    if (successEl) successEl.textContent = '';

    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    });
    const data = await res.json();

    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        if (successEl) successEl.textContent = 'Config saved';
        // Sync to inline editor
        if (configEditorEl) configEditorEl.value = content;
        setTimeout(() => { if (successEl) successEl.textContent = ''; }, 3000);
    }
}

async function reloadConfigModal() {
    const errorEl = document.getElementById('modalConfigError');
    const successEl = document.getElementById('modalConfigSuccess');
    const modalConfigEditorEl = document.getElementById('modalConfigEditor');
    const configEditorEl = document.getElementById('configEditor');
    const modalEl = document.getElementById('configModal');

    const content = modalConfigEditorEl?.value || '';
    if (errorEl) errorEl.textContent = '';
    if (successEl) successEl.textContent = '';

    // Save first
    let res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    });
    let data = await res.json();

    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
        return;
    }

    // Then reload
    res = await fetch('/api/config/reload', { method: 'POST' });
    data = await res.json();

    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        // Sync to inline editor and close modal
        if (configEditorEl) configEditorEl.value = content;
        if (modalEl) modalEl.classList.remove('open');
    }
}

async function saveConfig() {
    const errorEl = document.getElementById('configError');
    const successEl = document.getElementById('configSuccess');
    const configEditorEl = document.getElementById('configEditor');

    const content = configEditorEl?.value || '';
    if (errorEl) errorEl.textContent = '';
    if (successEl) successEl.textContent = '';

    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    });
    const data = await res.json();

    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        if (successEl) successEl.textContent = 'Config saved';
        setTimeout(() => { if (successEl) successEl.textContent = ''; }, 3000);
    }
}

async function reloadConfig() {
    const errorEl = document.getElementById('configError');
    const successEl = document.getElementById('configSuccess');
    const configEditorEl = document.getElementById('configEditor');

    if (errorEl) errorEl.textContent = '';
    if (successEl) successEl.textContent = '';

    // Save first
    const content = configEditorEl?.value || '';
    let res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    });
    let data = await res.json();

    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
        return;
    }

    // Then reload
    res = await fetch('/api/config/reload', { method: 'POST' });
    data = await res.json();

    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        if (successEl) successEl.textContent = 'Config saved & reloaded';
        setTimeout(() => { if (successEl) successEl.textContent = ''; }, 3000);
    }
}

// =============================================================================
// Archive
// =============================================================================

async function loadArchive() {
    const res = await fetch('/api/sessions/archive');
    const archive = await res.json();
    const container = document.getElementById('archiveList');

    if (!container) return;

    if (archive.length === 0) {
        container.innerHTML = '<div class="archive-empty">No archived sessions</div>';
        return;
    }

    container.innerHTML = archive.slice(0, 10).map(s => {
        const date = new Date(s.closed_at * 1000);
        const timeAgo = formatTimeAgo(date);
        return `
            <div class="archive-item">
                <span class="archive-name">${s.name}</span>
                <span class="archive-time">${timeAgo}</span>
            </div>
        `;
    }).join('');
}

function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    return Math.floor(seconds / 86400) + 'd ago';
}

// =============================================================================
// Event Binding
// =============================================================================

function bindEventListeners() {
    // Accordion headers
    document.querySelectorAll('.action-header').forEach(header => {
        header.addEventListener('click', () => {
            const group = header.closest('.action-group');
            if (group) toggleAction(group.id);
        });
    });

    // Sub-action headers
    document.querySelectorAll('.sub-action-header').forEach(header => {
        header.addEventListener('click', () => {
            const group = header.closest('.sub-action');
            if (group) toggleAction(group.id);
        });
    });

    // Permission mode radio options
    document.querySelectorAll('.radio-option').forEach(option => {
        option.addEventListener('click', () => {
            const radio = option.querySelector('input[type="radio"]');
            const bypass = radio?.value === 'true';
            selectPermissionMode(option, bypass);
        });
    });

    // Create session button
    const createSessionBtn = document.querySelector('#createSessionGroup .action-btn');
    if (createSessionBtn) {
        createSessionBtn.addEventListener('click', createSession);
    }

    // Session name enter key
    const sessionNameInput = document.getElementById('sessionName');
    if (sessionNameInput) {
        sessionNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') createSession();
        });
    }

    // Add machine button
    const addMachineBtn = document.querySelector('#addMachineGroup .action-btn');
    if (addMachineBtn) {
        addMachineBtn.addEventListener('click', addMachine);
    }

    // Config buttons
    const configContent = document.querySelector('#configGroup .action-content');
    if (configContent) {
        const buttons = configContent.querySelectorAll('.action-btn');
        buttons.forEach(btn => {
            const text = btn.textContent.trim();
            if (text === 'Save') {
                btn.addEventListener('click', saveConfig);
            } else if (text === 'Save & Reload') {
                btn.addEventListener('click', reloadConfig);
            } else if (btn.title === 'Fullscreen editor') {
                btn.addEventListener('click', openConfigModal);
            }
        });
    }

    // Modal buttons
    const modalCloseBtn = document.querySelector('.modal-buttons .action-btn.secondary');
    const modalSaveBtn = document.querySelector('.modal-buttons .action-btn.secondary:nth-child(2)');
    const modalReloadBtn = document.querySelector('.modal-buttons .action-btn:not(.secondary)');

    document.querySelectorAll('.modal-buttons .action-btn').forEach(btn => {
        const text = btn.textContent.trim();
        if (text === 'Close') {
            btn.addEventListener('click', closeConfigModal);
        } else if (text === 'Save') {
            btn.addEventListener('click', saveConfigModal);
        } else if (text === 'Save & Reload') {
            btn.addEventListener('click', reloadConfigModal);
        }
    });

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        const modal = document.getElementById('configModal');
        if (e.key === 'Escape' && modal?.classList.contains('open')) {
            closeConfigModal();
        }
    });
}

// =============================================================================
// Initialization
// =============================================================================

export function init() {
    bindEventListeners();
    loadSessions();
    loadMachines();
    loadConfig();
    loadArchive();

    // Refresh sessions every 5 seconds
    setInterval(loadSessions, 5000);
}

// Auto-init on DOMContentLoaded
document.addEventListener('DOMContentLoaded', init);
