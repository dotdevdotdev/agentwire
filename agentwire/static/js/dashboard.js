/**
 * Dashboard JS - AgentWire Dashboard Page
 * ES Module for dashboard functionality
 */

import * as ws from '/static/js/websocket.js';

// Get default voice from the page (set by Jinja2)
const DEFAULT_VOICE = window.AGENTWIRE_CONFIG?.defaultVoice || 'bashbunni';

// Path check debounce timeout
let pathCheckTimeout = null;

// Store machines data for later use
let machinesData = [];

// Store templates data for later use
let templatesData = [];

// Store current machine for create session modal
let currentMachine = 'local';

// Track session states for sound notifications
let sessionStates = new Map(); // session name -> 'active' | 'idle'

// =============================================================================
// Expand/Collapse State Management
// =============================================================================

const STORAGE_KEY_EXPAND_STATE = 'agentwire:dashboard:expandedState';

/**
 * Get expand/collapse state from localStorage
 * @returns {Object} State object with machines and sessions
 */
function getExpandedState() {
    const stored = localStorage.getItem(STORAGE_KEY_EXPAND_STATE);
    if (!stored) {
        // Default state: local machine expanded, all remote machines collapsed
        return {
            machines: {
                local: true  // Local machine expanded by default
            },
            sessions: {}  // Individual session expand states
        };
    }

    try {
        return JSON.parse(stored);
    } catch (e) {
        console.error('Failed to parse expand state:', e);
        return {
            machines: { local: true },
            sessions: {}
        };
    }
}

/**
 * Save expand/collapse state to localStorage
 * @param {Object} state - State object with machines and sessions
 */
function setExpandedState(state) {
    try {
        localStorage.setItem(STORAGE_KEY_EXPAND_STATE, JSON.stringify(state));
    } catch (e) {
        console.error('Failed to save expand state:', e);
    }
}

/**
 * Check if a machine is expanded
 * @param {string} machineId - Machine ID (e.g., 'local', 'gpu-server')
 * @returns {boolean} True if expanded
 */
function isMachineExpanded(machineId) {
    const state = getExpandedState();
    // Default to expanded for local, collapsed for remotes
    if (state.machines[machineId] === undefined) {
        return machineId === 'local';
    }
    return state.machines[machineId];
}

/**
 * Toggle machine expand/collapse state
 * @param {string} machineId - Machine ID
 * @returns {boolean} New state (true = expanded)
 */
function toggleMachineExpanded(machineId) {
    const state = getExpandedState();
    const currentState = isMachineExpanded(machineId);
    state.machines[machineId] = !currentState;
    setExpandedState(state);
    return state.machines[machineId];
}

/**
 * Check if a session is expanded (showing details)
 * @param {string} sessionName - Session name
 * @returns {boolean} True if expanded
 */
function isSessionExpanded(sessionName) {
    const state = getExpandedState();
    // Sessions collapsed by default
    return state.sessions[sessionName] === true;
}

/**
 * Toggle session expand/collapse state
 * @param {string} sessionName - Session name
 * @returns {boolean} New state (true = expanded)
 */
function toggleSessionExpanded(sessionName) {
    const state = getExpandedState();
    const currentState = isSessionExpanded(sessionName);
    state.sessions[sessionName] = !currentState;
    setExpandedState(state);
    return state.sessions[sessionName];
}

/**
 * Clean up state for removed machines/sessions
 * Removes entries that no longer exist in the current data
 * @param {Array} machines - Current machines list
 * @param {Array} sessions - Current sessions list
 */
function cleanupExpandedState(machines, sessions) {
    const state = getExpandedState();
    let modified = false;

    // Get valid machine IDs
    const validMachineIds = new Set(machines.map(m => m.id));
    validMachineIds.add('local');  // Always keep local

    // Remove machine states for deleted machines
    for (const machineId in state.machines) {
        if (!validMachineIds.has(machineId)) {
            delete state.machines[machineId];
            modified = true;
        }
    }

    // Get valid session names
    const validSessionNames = new Set(sessions.map(s => s.name));

    // Remove session states for deleted sessions
    for (const sessionName in state.sessions) {
        if (!validSessionNames.has(sessionName)) {
            delete state.sessions[sessionName];
            modified = true;
        }
    }

    if (modified) {
        setExpandedState(state);
    }
}

// =============================================================================
// WebSocket Activity Updates
// =============================================================================

/**
 * Handle real-time session activity updates from WebSocket
 * @param {Object} data - Activity update: {session: string, active: boolean}
 */
function handleSessionActivity(data) {
    const { session, active } = data;
    const activityState = active ? 'active' : 'idle';

    // Check for state transition and play notification sound
    checkSessionTransition(session, activityState);

    // Update the UI indicator live
    updateSessionIndicator(session, activityState);
}

/**
 * Update the activity indicator for a specific session in the DOM
 * @param {string} sessionName - The session name
 * @param {string} activityState - 'active' or 'idle'
 */
function updateSessionIndicator(sessionName, activityState) {
    // Find the session card for this session
    const sessions = document.getElementById('sessions');
    if (!sessions) return;

    const sessionCards = sessions.querySelectorAll('.session-card');

    for (const card of sessionCards) {
        const link = card.querySelector('a');
        if (!link) continue;

        // Extract session name from href: /room/{name}
        const href = link.getAttribute('href');
        const match = href?.match(/\/room\/(.+)/);
        if (!match) continue;

        const cardSessionName = decodeURIComponent(match[1]);
        if (cardSessionName !== sessionName) continue;

        // Find the activity indicator span
        const indicator = card.querySelector('.activity-indicator');
        if (!indicator) continue;

        // Update the class with smooth transition
        indicator.classList.remove('active', 'idle');
        indicator.classList.add(activityState);

        // Add pulse animation effect
        indicator.classList.add('updating');
        setTimeout(() => {
            indicator.classList.remove('updating');
        }, 300);

        break;
    }
}

// =============================================================================
// Sound Notification
// =============================================================================

// Generate a subtle notification sound using Web Audio API
function playIdleNotification() {
    const enabled = localStorage.getItem('agentwire-sound-notifications') === 'true';
    if (!enabled) return;

    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        // Subtle two-tone notification (E5 -> C5)
        oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime); // E5
        oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime + 0.1); // C5

        // Fade in and out for smooth sound
        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.15, audioContext.currentTime + 0.05);
        gainNode.gain.linearRampToValueAtTime(0, audioContext.currentTime + 0.25);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.25);
    } catch (error) {
        console.error('Failed to play notification sound:', error);
    }
}

// Check if a session transitioned from active to idle
function checkSessionTransition(sessionName, currentState) {
    const previousState = sessionStates.get(sessionName);

    // Active -> Idle transition
    if (previousState === 'active' && currentState === 'idle') {
        playIdleNotification();
    }

    // Update state
    sessionStates.set(sessionName, currentState);
}

// Load sound notification preference from localStorage
function loadSoundNotificationPreference() {
    const checkbox = document.getElementById('soundNotificationEnabled');
    if (!checkbox) return;

    const enabled = localStorage.getItem('agentwire-sound-notifications') === 'true';
    checkbox.checked = enabled;
}

// Save sound notification preference to localStorage
function saveSoundNotificationPreference(enabled) {
    localStorage.setItem('agentwire-sound-notifications', enabled.toString());
}

// =============================================================================
// Input Validation
// =============================================================================

// Invalid characters in session names - these cause issues with CLI parsing
const INVALID_SESSION_CHARS = /[@\/\s\\:*?"<>|.]/;

function validateSessionName(name) {
    if (!name) {
        return { valid: false, error: 'Session name is required' };
    }
    if (INVALID_SESSION_CHARS.test(name)) {
        return { valid: false, error: 'Name cannot contain @ / \\ : * ? " < > | . or spaces' };
    }
    if (name.startsWith('.') || name.startsWith('-')) {
        return { valid: false, error: 'Name cannot start with . or -' };
    }
    if (name.length > 50) {
        return { valid: false, error: 'Name cannot exceed 50 characters' };
    }
    return { valid: true, error: null };
}

function onSessionNameInput() {
    const nameInput = document.getElementById('sessionName');
    const errorEl = document.getElementById('error');
    const createBtn = document.querySelector('#createSessionModal .action-btn:not(.secondary)');

    const name = nameInput?.value.trim() || '';
    const validation = validateSessionName(name);

    if (errorEl) {
        errorEl.textContent = validation.error || '';
    }

    // Update button state
    if (createBtn) {
        createBtn.disabled = !validation.valid && name.length > 0;
        createBtn.style.opacity = createBtn.disabled ? '0.5' : '1';
    }

    // Auto-fill path based on session name
    onSessionNameChange();
}

function onSessionNameChange() {
    const name = document.getElementById('sessionName')?.value.trim() || '';
    const pathInput = document.getElementById('projectPath');

    // Don't auto-fill if user has manually edited
    if (!pathInput || pathInput.dataset.userEdited === 'true') return;

    if (name) {
        const projectsDir = currentMachine === 'local'
            ? '~/projects'
            : getMachineProjectsDir(currentMachine);
        pathInput.value = `${projectsDir}/${name}`;
        onPathChange();  // Trigger git detection
    } else {
        pathInput.value = '';
        hideGitOptions();
    }
}

// =============================================================================
// Git/Worktree Options
// =============================================================================

function onPathChange() {
    const path = document.getElementById('projectPath')?.value.trim() || '';

    clearTimeout(pathCheckTimeout);

    if (!path) {
        hideGitOptions();
        return;
    }

    pathCheckTimeout = setTimeout(async () => {
        try {
            const params = new URLSearchParams({ path, machine: currentMachine });
            const res = await fetch(`/api/check-path?${params}`);
            const data = await res.json();

            if (data.is_git) {
                showGitOptions(data.current_branch);
            } else {
                hideGitOptions();
            }
        } catch (e) {
            console.error('Path check failed:', e);
            hideGitOptions();
        }
    }, 300);  // 300ms debounce
}

function showGitOptions(currentBranch) {
    const gitOptions = document.getElementById('gitOptions');
    const branchLabel = document.getElementById('gitCurrentBranch');

    if (gitOptions) {
        gitOptions.style.display = 'block';
    }
    if (branchLabel) {
        branchLabel.textContent = currentBranch || 'unknown';
    }

    // Auto-suggest unique branch name
    suggestBranchName();
}

async function suggestBranchName() {
    const path = document.getElementById('projectPath')?.value.trim() || '';
    const machine = document.getElementById('sessionMachine')?.value || 'local';
    const branchInput = document.getElementById('branchName');

    if (!branchInput || !path) return;

    // Generate date-based prefix
    const now = new Date();
    const month = now.toLocaleString('en', { month: 'short' }).toLowerCase();
    const day = now.getDate();
    const year = now.getFullYear();
    const base = `${month}-${day}-${year}`;

    try {
        // Check existing branches matching this prefix
        const params = new URLSearchParams({ path, machine, prefix: base });
        const res = await fetch(`/api/check-branches?${params}`);
        const data = await res.json();

        // Find next available increment
        let increment = 1;
        const existing = data.existing || [];
        while (existing.includes(`${base}--${increment}`)) {
            increment++;
        }

        branchInput.value = `${base}--${increment}`;  // e.g., "jan-3-2026--1"
    } catch (e) {
        console.error('Branch name suggestion failed:', e);
        // Fallback: just use base with --1
        branchInput.value = `${base}--1`;
    }
}

// Track which sessions are expanded (for showing details)
let expandedSessions = new Set();

// Load expanded sessions from localStorage
function loadExpandedSessions() {
    try {
        const stored = localStorage.getItem('agentwire-expanded-sessions');
        if (stored) {
            expandedSessions = new Set(JSON.parse(stored));
        }
    } catch (e) {
        console.error('Failed to load expanded sessions:', e);
    }
}

// Save expanded sessions to localStorage
function saveExpandedSessions() {
    try {
        localStorage.setItem('agentwire-expanded-sessions', JSON.stringify([...expandedSessions]));
    } catch (e) {
        console.error('Failed to save expanded sessions:', e);
    }
}

// Toggle session expansion (globally accessible for onclick handlers)
window.toggleSessionExpansion = function(sessionName) {
    if (expandedSessions.has(sessionName)) {
        expandedSessions.delete(sessionName);
    } else {
        expandedSessions.add(sessionName);
    }
    saveExpandedSessions();

    // Update the DOM directly for smooth transition
    const sessionCard = document.querySelector(`[data-session-name="${CSS.escape(sessionName)}"]`);
    if (sessionCard) {
        const details = sessionCard.querySelector('.session-details');
        const toggle = sessionCard.querySelector('.session-toggle');
        if (details && toggle) {
            if (expandedSessions.has(sessionName)) {
                details.style.display = 'block';
                toggle.textContent = '▼';
            } else {
                details.style.display = 'none';
                toggle.textContent = '▶';
            }
        }
    }
};

/**
 * Render a session card (nested under machine)
 * @param {Object} session - Session data
 * @returns {string} HTML string for session card
 */
function renderSessionCard(session) {
    const s = session;
    const isExpanded = expandedSessions.has(s.name);

    // Determine badge: restricted > prompted > bypass
    let badge;
    if (s.restricted) {
        badge = '<span class="session-badge restricted">Restricted</span>';
    } else if (s.bypass_permissions === false) {
        badge = '<span class="session-badge prompted">Prompted</span>';
    } else {
        badge = '<span class="session-badge bypass">Bypass</span>';
    }

    // Strip @machine from display name if present (avoid doubling)
    let displayName = s.name;
    if (s.machine && s.name.endsWith('@' + s.machine)) {
        displayName = s.name.slice(0, -('@' + s.machine).length);
    }

    // Activity indicator
    const activityClass = s.activity === 'active' ? 'active' : 'idle';
    const activityIndicator = `<span class="activity-indicator ${activityClass}"></span>`;

    // Extract branch from session name if it's a worktree session (project/branch format)
    let branch = null;
    if (displayName.includes('/')) {
        const parts = displayName.split('/');
        if (parts.length === 2) {
            branch = parts[1];
        }
    }

    // Escape session name for safe onclick handler
    const escapedName = s.name.replace(/'/g, "\\'");

    return `
        <div class="session-card nested" data-session-name="${s.name}">
            <div class="session-header" onclick="toggleSessionExpansion('${escapedName}')">
                <span class="session-toggle">${isExpanded ? '▼' : '▶'}</span>
                ${activityIndicator}
                <span class="session-name-text">${displayName}</span>
                ${badge}
            </div>
            <div class="session-details" style="display: ${isExpanded ? 'block' : 'none'}">
                <div class="session-detail-row">
                    <span class="detail-label">Path:</span>
                    <span class="detail-value">${s.path || '~/projects/' + displayName}</span>
                </div>
                <div class="session-detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="detail-value ${activityClass}">${s.activity || 'idle'}</span>
                </div>
                ${branch ? `
                <div class="session-detail-row">
                    <span class="detail-label">Branch:</span>
                    <span class="detail-value">${branch}</span>
                </div>
                ` : ''}
                <div class="session-detail-row">
                    <span class="detail-label">Voice:</span>
                    <span class="detail-value">${s.voice || DEFAULT_VOICE}</span>
                </div>
                <div class="session-actions">
                    <a href="/room/${encodeURIComponent(s.name)}" class="session-btn">Open Room</a>
                    <button class="session-close-btn" data-session="${s.name}" title="Close session">Close Session</button>
                </div>
            </div>
        </div>
    `;
}

function hideGitOptions() {
    const gitOptions = document.getElementById('gitOptions');
    if (gitOptions) {
        gitOptions.style.display = 'none';
    }
}

function onWorktreeChange() {
    const useWorktree = document.getElementById('useWorktree')?.checked;
    const branchRow = document.getElementById('branchRow');

    if (branchRow) {
        branchRow.style.display = useWorktree ? 'block' : 'none';
    }
}

// =============================================================================
// Machine Selector
// =============================================================================

function populateMachineDropdown(machines) {
    const select = document.getElementById('sessionMachine');
    if (!select) return;

    // Clear existing options except first (Local)
    while (select.options.length > 1) {
        select.remove(1);
    }

    // Add remote machines
    machines.filter(m => !m.local).forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = `${m.id} (${m.host})`;
        select.appendChild(option);
    });

    // Restore last selected machine from localStorage
    restoreLastMachine();
}

function getMachineProjectsDir(machineId) {
    const machine = machinesData.find(m => m.id === machineId);
    return machine?.projects_dir || '~/projects';
}

function updateMachineSuffix() {
    const machine = document.getElementById('sessionMachine')?.value;
    const suffix = document.getElementById('machineSuffix');
    if (!suffix) return;

    if (machine === 'local') {
        suffix.textContent = '';
    } else {
        suffix.textContent = `@${machine}`;
    }
}

function restoreLastMachine() {
    const last = localStorage.getItem('agentwire-last-machine');
    if (last) {
        const select = document.getElementById('sessionMachine');
        if (select && [...select.options].some(o => o.value === last)) {
            select.value = last;
            updateMachineSuffix();
        }
    }
}

function onMachineChange() {
    const machineSelect = document.getElementById('sessionMachine');
    if (machineSelect) {
        updateMachineSuffix();
        updatePathPlaceholder();
        // Save to localStorage
        localStorage.setItem('agentwire-last-machine', machineSelect.value);
        // Re-check path for git status on different machine
        onPathChange();
        // Re-auto-fill path if not user-edited
        onSessionNameChange();
    }
}

function updatePathPlaceholder() {
    const machine = document.getElementById('sessionMachine')?.value || 'local';
    const pathInput = document.getElementById('projectPath');

    if (!pathInput) return;

    if (machine === 'local') {
        pathInput.placeholder = '~/projects/name';
    } else {
        const projectsDir = getMachineProjectsDir(machine);
        pathInput.placeholder = `${projectsDir}/name`;
    }
}

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
// Machine Card Component
// =============================================================================

/**
 * Render a machine card with sessions
 * @param {Object} machine - Machine object with id, host, status, sessions
 * @param {boolean} isLocal - True if this is the local machine
 * @returns {string} HTML string for machine card
 */
function renderMachineCard(machine, isLocal = false) {
    const machineId = machine.id || 'local';
    const isExpanded = isMachineExpanded(machineId);
    const expandIcon = isExpanded ? '▼' : '▶';
    const sessionCount = machine.sessions?.length || 0;

    // Machine header info
    const machineName = isLocal ? 'Local' : machine.id;
    const hostInfo = !isLocal && machine.host ? ` (${machine.host})` : '';
    const statusClass = machine.status || 'online';
    const sessionCountText = `${sessionCount} session${sessionCount !== 1 ? 's' : ''}`;

    let html = `
        <div class="machine-card ${isExpanded ? 'expanded' : 'collapsed'}">
            <div class="machine-header" data-machine-id="${machineId}">
                <div class="machine-info">
                    <span class="expand-icon">${expandIcon}</span>
                    <span class="status-dot ${statusClass}"></span>
                    <span class="machine-name">${machineName}${hostInfo}</span>
                    <span class="machine-session-count">• ${sessionCountText}</span>
                </div>
                <button class="machine-create-btn" data-machine-id="${machineId}" title="Create session on ${machineName}">+</button>
            </div>`;

    // Sessions container (only if expanded)
    if (isExpanded) {
        html += '<div class="machine-sessions">';

        if (sessionCount === 0) {
            html += '<div class="machine-empty-state">No sessions running on this machine</div>';
        } else {
            html += machine.sessions.map(s => renderSessionCard(s, machineId)).join('');
        }

        html += '</div>';
    }

    html += '</div>';
    return html;
}

/**
 * Render a session card (nested under machine)
 * @param {Object} session - Session object
 * @param {string} machineId - ID of parent machine
 * @returns {string} HTML string for session card
 */
function renderSessionCard(session, machineId) {
    const isExpanded = isSessionExpanded(session.name);
    const expandIcon = isExpanded ? '▼' : '▶';

    // Determine badge: restricted > prompted > bypass
    let badge;
    if (session.restricted) {
        badge = '<span class="session-badge restricted">Restricted</span>';
    } else if (session.bypass_permissions === false) {
        badge = '<span class="session-badge prompted">Prompted</span>';
    } else {
        badge = '<span class="session-badge bypass">Bypass</span>';
    }

    // Strip @machine from display name if present (avoid doubling)
    let displayName = session.name;
    if (session.machine && session.name.endsWith('@' + session.machine)) {
        displayName = session.name.slice(0, -('@' + session.machine).length);
    }

    // Activity indicator
    const activityClass = session.activity === 'active' ? 'active' : 'idle';
    const activityIndicator = `<span class="activity-indicator ${activityClass}"></span>`;

    let html = `
        <div class="session-card ${isExpanded ? 'expanded' : 'collapsed'}">
            <div class="session-header" data-session-name="${session.name}">
                <span class="expand-icon">${expandIcon}</span>
                ${activityIndicator}
                <span class="session-display-name">${displayName}</span>
                ${badge}
            </div>`;

    // Session details (only if expanded)
    if (isExpanded) {
        const path = session.path || `~/projects/${displayName}`;
        const voice = session.voice || DEFAULT_VOICE;
        const branch = session.branch ? `<div class="session-detail-row">Branch: <span class="session-detail-value">${session.branch}</span></div>` : '';

        html += `
            <div class="session-details">
                <div class="session-detail-row">Path: <span class="session-detail-value">${path}</span></div>
                ${branch}
                <div class="session-detail-row">Voice: <span class="session-detail-value">${voice}</span></div>
                <div class="session-detail-row">Status: <span class="session-detail-value ${activityClass}">${session.activity || 'idle'}</span></div>
                <div class="session-actions">
                    <a href="/room/${encodeURIComponent(session.name)}" class="session-open-btn">Open Room</a>
                    <button class="session-close-btn" data-session="${session.name}">Close</button>
                </div>
            </div>`;
    }

    html += '</div>';
    return html;
}

/**
 * Attach event handlers to machine and session cards
 */
function attachMachineEventHandlers(container) {
    // Machine header click - toggle expand/collapse
    container.querySelectorAll('.machine-header').forEach(header => {
        header.addEventListener('click', (e) => {
            // Don't toggle if clicking the create button
            if (e.target.classList.contains('machine-create-btn')) {
                return;
            }
            const machineId = header.dataset.machineId;
            toggleMachineExpanded(machineId);
            loadSessions(); // Reload to show/hide sessions
        });
    });

    // Session header click - toggle expand/collapse
    container.querySelectorAll('.session-header').forEach(header => {
        header.addEventListener('click', (e) => {
            const sessionName = header.dataset.sessionName;
            toggleSessionExpanded(sessionName);
            loadSessions(); // Reload to show/hide details
        });
    });

    // Machine create button
    container.querySelectorAll('.machine-create-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent machine toggle
            const machineId = btn.dataset.machineId;
            openCreateSessionForMachine(machineId);
        });
    });

    // Session close button
    container.querySelectorAll('.session-close-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation(); // Prevent session toggle
            closeSession(btn.dataset.session);
        });
    });
}

/**
 * Open create session form with machine pre-selected
 */
function openCreateSessionForMachine(machineId) {
    // Open the create session accordion
    const createGroup = document.getElementById('createSessionGroup');
    if (createGroup && !createGroup.classList.contains('open')) {
        createGroup.classList.add('open');
    }

    // Set the machine dropdown
    const machineSelect = document.getElementById('sessionMachine');
    if (machineSelect) {
        machineSelect.value = machineId === 'local' ? 'local' : machineId;
        onMachineChange();
    }

    // Scroll to form
    createGroup?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Focus name input
    const nameInput = document.getElementById('sessionName');
    if (nameInput) {
        setTimeout(() => nameInput.focus(), 300);
    }
}
// =============================================================================

async function loadSessions() {
    const container = document.getElementById('sessions');
    const sessionCountEl = document.getElementById('sessionCount');

    // Show loading state
    if (container) {
        container.innerHTML = `
            <div class="skeleton-session">
                <div class="skeleton-line" style="width: 60%"></div>
                <div class="skeleton-line" style="width: 80%; margin-top: 0.5rem"></div>
            </div>
            <div class="skeleton-session">
                <div class="skeleton-line" style="width: 70%"></div>
                <div class="skeleton-line" style="width: 75%; margin-top: 0.5rem"></div>
            </div>
        `;
    }

    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();

        // Calculate total session count across all machines
        const totalSessions = (data.local?.session_count || 0) +
            (data.machines?.reduce((sum, m) => sum + (m.session_count || 0), 0) || 0);

        if (totalSessions === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📭</div>
                    <div class="empty-title">No sessions running</div>
                    <div class="empty-description">Create a session to get started with AgentWire</div>
                    <div class="empty-action">
                        <a href="#" class="empty-link" onclick="toggleAction('createSessionGroup'); return false;">Create your first session →</a>
                    </div>
                </div>
            `;
            if (sessionCountEl) {
                sessionCountEl.innerHTML = '<span class="count">0</span> active sessions';
            }
            return;
        }

        // Check for activity state transitions across all sessions
        const allSessions = [
            ...(data.local?.sessions || []),
            ...(data.machines?.flatMap(m => m.sessions || []) || [])
        ];
        allSessions.forEach(session => {
            if (session.activity) {
                checkSessionTransition(session.name, session.activity);
            }
        });

        // Update session count in left column
        if (sessionCountEl) {
            sessionCountEl.innerHTML =
                `<span class="count">${totalSessions}</span> active session${totalSessions !== 1 ? 's' : ''}`;
        }

        // Render hierarchical machine→sessions view
        const machineCards = [];

        // Render local machine first
        if (data.local) {
            machineCards.push(renderMachineCard({
                id: 'local',
                host: null,
                status: 'online',
                session_count: data.local.session_count,
                sessions: data.local.sessions || []
            }, true));
        }

        // Render remote machines
        if (data.machines && data.machines.length > 0) {
            data.machines.forEach(machine => {
                machineCards.push(renderMachineCard(machine, false));
            });
        }

        container.innerHTML = machineCards.join('');

        // Attach event handlers for machine cards and sessions
        attachMachineEventHandlers(container);
    } catch (error) {
        console.error('Failed to load sessions:', error);
        if (container) {
            container.innerHTML = `
                <div class="error-state">
                    <div class="error-icon">⚠️</div>
                    <div class="error-title">Failed to load sessions</div>
                    <div class="error-description">${error.message || 'Unknown error'}</div>
                </div>
            `;
        }
    }
}

async function createSession() {
    const nameInput = document.getElementById('sessionName');
    const pathInput = document.getElementById('projectPath');
    const voiceSelect = document.getElementById('sessionVoice');
    const machineSelect = document.getElementById('sessionMachine');
    const worktreeCheckbox = document.getElementById('useWorktree');
    const branchInput = document.getElementById('branchName');
    const templateSelect = document.getElementById('sessionTemplate');
    const permissionModeRadio = document.querySelector('input[name="permissionMode"]:checked');
    const gitOptions = document.getElementById('gitOptions');
    const errorEl = document.getElementById('error');

    const name = nameInput?.value.trim() || '';
    const path = pathInput?.value.trim() || '';
    const voice = voiceSelect?.value || DEFAULT_VOICE;
    const machine = machineSelect?.value || 'local';
    const template = templateSelect?.value || null;

    // Only include worktree/branch if git options are visible
    const gitOptionsVisible = gitOptions && gitOptions.style.display !== 'none';
    const worktree = gitOptionsVisible && worktreeCheckbox?.checked;
    const branch = worktree ? (branchInput?.value.trim() || '') : '';

    // Permission mode: bypass (default), normal (prompted), or restricted
    const permissionMode = permissionModeRadio?.value || 'bypass';
    const bypassPermissions = permissionMode === 'bypass';
    const restricted = permissionMode === 'restricted';

    // Validate session name first
    const validation = validateSessionName(name);
    if (!validation.valid) {
        if (errorEl) errorEl.textContent = validation.error;
        return;
    }

    if (errorEl) errorEl.textContent = '';

    const res = await fetch('/api/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name,
            path: path || null,
            voice,
            machine: machine !== 'local' ? machine : null,
            worktree,
            branch,
            bypass_permissions: bypassPermissions,
            restricted: restricted,
            template: template || null
        })
    });

    const data = await res.json();
    if (data.error) {
        if (errorEl) errorEl.textContent = data.error;
    } else {
        // Use the session name returned by server (includes branch@machine if applicable)
        window.location.href = '/room/' + encodeURIComponent(data.name);
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
    const container = document.getElementById('machinesList');

    // Show loading state
    if (container) {
        container.innerHTML = `
            <div class="skeleton-machine">
                <div class="skeleton-line" style="width: 50%"></div>
            </div>
            <div class="skeleton-machine">
                <div class="skeleton-line" style="width: 60%"></div>
            </div>
        `;
    }

    try {
        const res = await fetch('/api/machines');
        const machines = await res.json();
        machinesData = machines;  // Store for later use

        // Populate the session machine dropdown
        populateMachineDropdown(machines);

        if (!container) return;

        if (machines.length === 0) {
            container.innerHTML = `
                <div class="empty-state empty-state-small">
                    <div class="empty-icon-small">🖥️</div>
                    <div class="empty-title-small">No machines configured</div>
                    <div class="empty-action">
                        <a href="#" class="empty-link" onclick="toggleAction('addMachineGroup'); return false;">Add a machine →</a>
                    </div>
                </div>
            `;
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
                <button class="machine-create" data-machine="${m.id}" title="Create session on ${m.id}">+</button>
                ${!m.local ? `<button class="machine-remove" data-machine="${m.id}" title="Remove machine">✕</button>` : ''}
            </div>
        </div>
    `).join('');

        // Attach create session handlers
        container.querySelectorAll('.machine-create').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                openCreateSessionModal(btn.dataset.machine);
            });
        });

        // Attach remove handlers
        container.querySelectorAll('.machine-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                removeMachine(btn.dataset.machine);
            });
        });
    } catch (error) {
        console.error('Failed to load machines:', error);
        if (container) {
            container.innerHTML = `
                <div class="error-state error-state-small">
                    <div class="error-icon-small">⚠️</div>
                    <div class="error-title-small">Failed to load machines</div>
                    <div class="error-description-small">${error.message || 'Unknown error'}</div>
                </div>
            `;
        }
    }
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
// Templates
// =============================================================================

async function loadTemplates() {
    try {
        const res = await fetch('/api/templates');
        templatesData = await res.json();
        populateTemplateDropdown(templatesData);
    } catch (err) {
        console.error('Failed to load templates:', err);
        templatesData = [];
    }
}

function populateTemplateDropdown(templates) {
    const select = document.getElementById('sessionTemplate');
    if (!select) return;

    // Keep the first option (None - Start fresh)
    const firstOption = select.querySelector('option');
    select.innerHTML = '';
    if (firstOption) select.appendChild(firstOption);

    // Add template options
    templates.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.name;
        opt.textContent = t.name + (t.description ? ` - ${t.description}` : '');
        select.appendChild(opt);
    });
}

function onTemplateChange() {
    const select = document.getElementById('sessionTemplate');
    const preview = document.getElementById('templatePreview');
    const descEl = document.getElementById('templateDescription');
    const promptEl = document.getElementById('templatePrompt');
    const voiceSelect = document.getElementById('sessionVoice');

    if (!select || !preview) return;

    const templateName = select.value;

    if (!templateName) {
        preview.style.display = 'none';
        return;
    }

    // Find the template
    const template = templatesData.find(t => t.name === templateName);
    if (!template) {
        preview.style.display = 'none';
        return;
    }

    // Show preview
    preview.style.display = 'block';
    if (descEl) {
        descEl.textContent = template.description || 'No description';
    }
    if (promptEl) {
        const promptText = template.initial_prompt || '(No initial prompt)';
        // Truncate long prompts
        promptEl.textContent = promptText.length > 300
            ? promptText.substring(0, 300) + '...'
            : promptText;
    }

    // Set voice from template if specified
    if (template.voice && voiceSelect) {
        const voiceOption = Array.from(voiceSelect.options).find(opt => opt.value === template.voice);
        if (voiceOption) {
            voiceSelect.value = template.voice;
        }
    }

    // Set permission mode from template
    const bypassRadio = document.querySelector('input[name="permissionMode"][value="bypass"]');
    const normalRadio = document.querySelector('input[name="permissionMode"][value="normal"]');
    const restrictedRadio = document.querySelector('input[name="permissionMode"][value="restricted"]');

    if (template.restricted && restrictedRadio) {
        restrictedRadio.checked = true;
        updateRadioSelection(restrictedRadio);
    } else if (!template.bypass_permissions && normalRadio) {
        normalRadio.checked = true;
        updateRadioSelection(normalRadio);
    } else if (template.bypass_permissions && bypassRadio) {
        bypassRadio.checked = true;
        updateRadioSelection(bypassRadio);
    }
}

function updateRadioSelection(radio) {
    // Update the radio group UI to reflect selection
    const radioOptions = document.querySelectorAll('.radio-option');
    radioOptions.forEach(opt => {
        const input = opt.querySelector('input[type="radio"]');
        if (input === radio) {
            opt.classList.add('selected');
        } else {
            opt.classList.remove('selected');
        }
    });
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
    // Sound notification toggle
    const soundToggle = document.getElementById('soundNotificationEnabled');
    if (soundToggle) {
        soundToggle.addEventListener('change', (e) => {
            saveSoundNotificationPreference(e.target.checked);
        });
    }

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

    // Session name validation and enter key
    const sessionNameInput = document.getElementById('sessionName');
    if (sessionNameInput) {
        sessionNameInput.addEventListener('input', onSessionNameInput);
        sessionNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const validation = validateSessionName(sessionNameInput.value.trim());
                if (validation.valid) {
                    createSession();
                }
            }
        });
    }

    // Machine selector change event
    const machineSelect = document.getElementById('sessionMachine');
    if (machineSelect) {
        machineSelect.addEventListener('change', onMachineChange);
    }

    // Path change detection (for git options)
    const pathInput = document.getElementById('projectPath');
    if (pathInput) {
        pathInput.addEventListener('input', () => {
            pathInput.dataset.userEdited = 'true';
            onPathChange();
        });
    }

    // Worktree checkbox
    const worktreeCheckbox = document.getElementById('useWorktree');
    if (worktreeCheckbox) {
        worktreeCheckbox.addEventListener('change', onWorktreeChange);
    }

    // Template selector
    const templateSelect = document.getElementById('sessionTemplate');
    if (templateSelect) {
        templateSelect.addEventListener('change', onTemplateChange);
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
    loadExpandedSessions();
    loadSoundNotificationPreference();
    loadSessions();
    loadMachines();
    loadTemplates();
    loadConfig();
    loadArchive();

    // Connect WebSocket for real-time activity updates
    // Use 'dashboard' as a special room name for global session updates
    ws.connect('dashboard', {
        onSessionActivity: handleSessionActivity,
        onConnect: () => {
            console.log('[Dashboard] WebSocket connected - real-time activity updates enabled');
        },
        onDisconnect: () => {
            console.log('[Dashboard] WebSocket disconnected - falling back to polling');
        }
    });

    // Refresh sessions every 5 seconds (fallback for when WebSocket is down)
    setInterval(loadSessions, 5000);
}

// Auto-init on DOMContentLoaded
document.addEventListener('DOMContentLoaded', init);
