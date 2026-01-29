/**
 * Machines Window - displays all registered machines with status
 */

import { ListWindow } from '../list-window.js';
import { machineIcons } from '../icon-manager.js';
import { IconPicker } from '../components/icon-picker.js';
import { ListCard } from '../components/list-card.js';
import { setupAutoRefresh } from '../utils/auto-refresh.js';

/** @type {IconPicker|null} */
let iconPicker = null;

/** @type {ListWindow|null} */
let machinesWindow = null;

/**
 * Open the Machines window
 * @returns {ListWindow} The machines window instance
 */
export function openMachinesWindow() {
    if (machinesWindow?.winbox) {
        machinesWindow.winbox.focus();
        return machinesWindow;
    }

    machinesWindow = new ListWindow({
        id: 'machines',
        title: 'Machines',
        fetchData: fetchMachines,
        renderItem: renderMachineItem,
        onItemAction: handleMachineAction,
        emptyMessage: 'No machines configured'
    });

    machinesWindow._cleanup = () => {
        machinesWindow = null;
    };

    machinesWindow.open();
    return machinesWindow;
}

/**
 * Fetch machines from API
 * API returns array: [{id, host, ip, local, status}, ...]
 * @returns {Promise<Array>} Array of machine objects
 */
async function fetchMachines() {
    const response = await fetch('/api/machines');
    const machines = await response.json();
    if (!Array.isArray(machines)) return [];
    // Sort alphabetically
    machines.sort((a, b) => a.id.localeCompare(b.id));
    // Get icons using IconManager (persistent, name-matched or random)
    const machineIds = machines.map(m => m.id);
    const iconUrls = await machineIcons.getIconsForItems(machineIds);

    const result = machines.map(m => ({ ...m, iconUrl: iconUrls[m.id] }));

    // Auto-refresh while machines are checking status
    setupAutoRefresh(result, machinesWindow);

    return result;
}

/**
 * Render a single machine item
 * @param {Object} machine - Machine data {id, host, local, status}
 * @returns {string} HTML string for the machine item
 */
function renderMachineItem(machine) {
    // Build meta - show "local" tag for local machines, id for remote if different from host
    const metaParts = [];

    // Always include IP span for consistent layout (empty if offline/checking)
    metaParts.push(`<span class="machine-ip">${machine.ip || ''}</span>`);

    if (machine.id !== machine.host) {
        metaParts.push(`<span class="session-path">${machine.id}</span>`);
    } else if (machine.local) {
        metaParts.push(`<span class="type-tag type-local">local</span>`);
    }

    // Use activity indicator (spinner) for checking state
    const cardOptions = {
        id: machine.id,
        iconUrl: machine.iconUrl,
        name: machine.host || machine.id,
        meta: metaParts.join(' '),
        actions: [
            {
                label: 'New',
                action: 'new-session',
                primary: true,
                combo: {
                    action: 'new-session-options',
                    title: 'Customize session options'
                }
            },
            { label: '✕', action: 'delete', danger: true, title: 'Remove machine' }
        ]
    };

    // Show spinner while checking, status dot when known
    if (machine.status === 'checking') {
        cardOptions.activityState = 'processing';
    } else {
        cardOptions.statusOnline = machine.status === 'online';
    }

    return ListCard(cardOptions);
}

/**
 * Handle action on machine items
 * @param {string} action - The action type ('edit-icon', 'delete', 'new-session', 'new-session-options')
 * @param {Object} item - The machine data object
 */
function handleMachineAction(action, item) {
    if (action === 'edit-icon') {
        openIconPicker(item.id);
    } else if (action === 'delete') {
        showDeleteModal(item);
    } else if (action === 'new-session') {
        createBareSession(item);
    } else if (action === 'new-session-options') {
        showNewSessionModal(item);
    }
}

/**
 * Open the icon picker for a machine
 * @param {string} machineId - Machine ID
 */
function openIconPicker(machineId) {
    if (!iconPicker) {
        iconPicker = new IconPicker(machineIcons);
    }
    iconPicker.show(machineId, () => {
        // Refresh the list after icon change
        machinesWindow?.refresh();
    });
}

/**
 * Show the delete machine modal
 * @param {Object} machine - Machine to delete
 */
function showDeleteModal(machine) {
    // Remove existing modal if any
    const existing = document.querySelector('.delete-machine-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.className = 'modal-overlay delete-machine-modal';
    modal.innerHTML = `
        <div class="modal delete-modal">
            <div class="modal-header">
                <h3>Remove Machine</h3>
                <button class="modal-close" data-action="close">✕</button>
            </div>
            <div class="modal-body">
                <p>Remove <strong>${machine.id}</strong> (${machine.host}) from AgentWire?</p>
                <p class="warning-text">This will only remove it from the machines list. The actual machine will not be affected.</p>
            </div>
            <div class="modal-footer">
                <button class="btn secondary" data-action="cancel">Cancel</button>
                <button class="btn-danger" data-action="confirm">Yes, Remove</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Handle modal actions
    modal.addEventListener('click', async (e) => {
        const action = e.target.dataset.action;
        if (action === 'close' || action === 'cancel') {
            modal.remove();
        } else if (action === 'confirm') {
            await executeDelete(machine, modal);
        }
    });

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

/**
 * Execute the delete operation
 * @param {Object} machine - Machine to delete
 * @param {HTMLElement} modal - Modal to close
 */
async function executeDelete(machine, modal) {
    const confirmBtn = modal.querySelector('[data-action="confirm"]');
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Removing...';
    }

    try {
        const response = await fetch(`/api/machines/${machine.id}`, {
            method: 'DELETE'
        });

        const result = await response.json();
        if (result.success) {
            modal.remove();
            showToast(`Machine ${machine.id} removed successfully`, 'success');
            machinesWindow?.refresh();
        } else {
            throw new Error(result.error || 'Delete failed');
        }
    } catch (err) {
        showToast(`Failed to remove machine: ${err.message}`, 'error');
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Yes, Remove';
        }
    }
}

/**
 * Create a bare session on a machine
 * @param {Object} machine - Machine to create session on
 */
async function createBareSession(machine) {
    try {
        // Default to ~/projects for project root
        const projectRoot = '~/projects';
        const sessionName = `${machine.id}-bare`;

        const response = await fetch('/api/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: sessionName,
                path: projectRoot,
                machine: machine.local ? null : machine.id,
                type: 'bare',
                roles: []
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast(`Bare session "${sessionName}" created on ${machine.id}`, 'success');
            // Open the session window
            import('../desktop-manager.js').then(module => {
                module.desktop.openSession(sessionName, machine.local ? null : machine.id);
            });
        } else {
            throw new Error(result.error || 'Failed to create session');
        }
    } catch (err) {
        showToast(`Failed to create session: ${err.message}`, 'error');
    }
}

/**
 * Show modal to customize session options
 * @param {Object} machine - Machine data
 */
async function showNewSessionModal(machine) {
    // Remove existing modal if any
    const existing = document.querySelector('.new-machine-session-modal');
    if (existing) existing.remove();

    // Fetch roles
    const roles = await fetchRoles();

    const modal = document.createElement('div');
    modal.className = 'modal-overlay new-machine-session-modal';

    // Session types
    const SESSION_TYPES = [
        { value: 'bare', label: 'Bare' },
        { value: 'claude-bypass', label: 'Claude (Bypass)' },
        { value: 'claude-prompted', label: 'Claude (Prompted)' },
        { value: 'opencode-bypass', label: 'OpenCode (Bypass)' },
        { value: 'opencode-prompted', label: 'OpenCode (Prompted)' }
    ];

    const typeOptions = SESSION_TYPES.map(t =>
        `<option value="${t.value}"${t.value === 'bare' ? ' selected' : ''}>${t.label}</option>`
    ).join('');

    const roleCheckboxes = roles.map(r =>
        `<label class="role-checkbox">
            <input type="checkbox" value="${r.name}">
            <span>${r.name}</span>
        </label>`
    ).join('');

    modal.innerHTML = `
        <div class="modal new-session-options-modal">
            <div class="modal-header">
                <h3>New Session on ${machine.id}</h3>
                <button class="modal-close" data-action="close">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Directory Path</label>
                    <input type="text" class="session-path-input" value="~/projects" placeholder="~/projects">
                </div>

                <div class="form-group">
                    <label>Session Type</label>
                    <select class="session-type-select">
                        ${typeOptions}
                    </select>
                </div>

                <div class="form-group">
                    <label>Roles (optional)</label>
                    <div class="roles-checkboxes">
                        ${roleCheckboxes}
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn secondary" data-action="cancel">Cancel</button>
                <button class="btn primary" data-action="create">Create Session</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Handle modal actions
    modal.addEventListener('click', async (e) => {
        const action = e.target.dataset.action;
        if (action === 'close' || action === 'cancel') {
            modal.remove();
        } else if (action === 'create') {
            const pathInput = modal.querySelector('.session-path-input');
            const typeSelect = modal.querySelector('.session-type-select');
            const checkedRoles = [...modal.querySelectorAll('.role-checkbox input:checked')]
                .map(cb => cb.value);

            await createSessionWithOptions(machine, pathInput.value, typeSelect.value, checkedRoles, modal);
        }
    });

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

/**
 * Create session with custom options
 * @param {Object} machine - Machine data
 * @param {string} path - Directory path
 * @param {string} type - Session type
 * @param {Array} roles - Selected roles
 * @param {HTMLElement} modal - Modal to close on success
 */
async function createSessionWithOptions(machine, path, type, roles, modal) {
    const createBtn = modal.querySelector('[data-action="create"]');
    if (createBtn) {
        createBtn.disabled = true;
        createBtn.textContent = 'Creating...';
    }

    try {
        const sessionName = `${machine.id}-${type}`;

        const response = await fetch('/api/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: sessionName,
                path: path,
                machine: machine.local ? null : machine.id,
                type: type,
                roles: roles
            })
        });

        const result = await response.json();
        if (!result.success) {
            if (createBtn) {
                createBtn.disabled = false;
                createBtn.textContent = 'Create Session';
            }
        } else {
            modal.remove();
            showToast(`Session "${sessionName}" created on ${machine.id}`, 'success');
            // Open the session window
            import('../desktop-manager.js').then(module => {
                module.desktop.openSession(sessionName, machine.local ? null : machine.id);
            });
        }
    } catch (err) {
        showToast(`Failed to create session: ${err.message}`, 'error');
        if (createBtn) {
            createBtn.disabled = false;
            createBtn.textContent = 'Create Session';
        }
    }
}

/**
 * Fetch available roles from API
 * @returns {Promise<Array>} Array of role objects
 */
async function fetchRoles() {
    try {
        const response = await fetch('/api/roles');
        const data = await response.json();
        return data.roles || [];
    } catch (err) {
        console.error('[Machines] Failed to fetch roles:', err);
        return [];
    }
}

/**
 * Show a toast notification
 * @param {string} message - Message to show
 * @param {string} type - Toast type ('success' or 'error')
 */
function showToast(message, type) {
    // Simple toast implementation - reuse from desktop if available
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = 'position:fixed;top:20px;right:20px;padding:12px 20px;background:#333;color:white;border-radius:4px;z-index:10000;';
    if (type === 'error') toast.style.background = '#dc2626';
    if (type === 'success') toast.style.background = '#059669';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
