/**
 * Machines Window - displays all registered machines with status
 */

import { ListWindow } from '../list-window.js';
import { machineIcons } from '../icon-manager.js';
import { IconPicker } from '../components/icon-picker.js';

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

    // Add styles
    addMachinesStyles();

    machinesWindow.open();
    return machinesWindow;
}

/**
 * Fetch machines from API
 * API returns array: [{id, host, local, status}, ...]
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
    return machines.map((m) => ({ ...m, iconUrl: iconUrls[m.id] }));
}

/**
 * Render a single machine item
 * @param {Object} machine - Machine data {id, host, local, status}
 * @returns {string} HTML string for the machine item
 */
function renderMachineItem(machine) {
    const isOnline = machine.status === 'online';
    const statusClass = isOnline ? 'online' : 'offline';
    const localTag = machine.local ? '<span class="machine-tag local">local</span>' : '';
    const iconUrl = machine.iconUrl;

    return `
        <div class="machine-card" data-machine-id="${machine.id}">
            <div class="machine-icon-wrapper">
                <button class="icon-edit-btn" data-action="edit-icon" title="Change icon">⚙</button>
                <img src="${iconUrl}" alt="" class="machine-icon" />
                <span class="machine-status-dot ${statusClass}"></span>
            </div>
            <div class="machine-content">
                <div class="machine-header">
                    <span class="machine-name">${machine.id}</span>
                </div>
                <div class="machine-host">${machine.host || 'localhost'}</div>
                <div class="machine-tag-row">
                    ${localTag}
                </div>
            </div>
        </div>
    `;
}

/**
 * Handle action on machine items
 * @param {string} action - The action type
 * @param {Object} item - The machine data object
 */
function handleMachineAction(action, item) {
    if (action === 'edit-icon') {
        openIconPicker(item.id);
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
 * Add CSS styles for machines window
 */
function addMachinesStyles() {
    if (document.getElementById('machines-window-styles')) return;

    const style = document.createElement('style');
    style.id = 'machines-window-styles';
    style.textContent = `
        .machine-card {
            display: flex;
            align-items: center;
            gap: 12px;
            width: 100%;
        }

        .machine-icon-wrapper {
            position: relative;
            flex-shrink: 0;
        }

        .machine-icon {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            object-fit: cover;
        }

        .machine-status-dot {
            position: absolute;
            bottom: -2px;
            right: -2px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid var(--surface);
        }

        .machine-status-dot.online {
            background: var(--accent);
        }

        .machine-status-dot.offline {
            background: var(--text-muted);
        }

        .machine-content {
            flex: 1;
            min-width: 0;
        }

        .machine-header {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .machine-name {
            font-weight: 500;
            color: var(--text);
            font-size: 14px;
        }

        .machine-host {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .machine-tag-row {
            display: flex;
            justify-content: flex-end;
            margin-top: 6px;
        }

        .machine-tag {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            text-transform: uppercase;
        }

        .machine-tag.local {
            background: rgba(74, 222, 128, 0.15);
            color: var(--accent);
        }
    `;
    document.head.appendChild(style);
}
