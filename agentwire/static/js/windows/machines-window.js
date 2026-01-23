/**
 * Machines Window - displays all registered machines with status
 */

import { ListWindow } from '../list-window.js';

/** Machine icon filenames (12 robot/android icons, wraps for more machines) */
const MACHINE_ICONS = [
    'android.png',
    'automaton.png',
    'bot.png',
    'cyborg.png',
    'droid.png',
    'drone.png',
    'guardian.png',
    'mech.png',
    'probe.png',
    'robot.png',
    'sentinel.png',
    'unit.png'
];

/**
 * Get icon URL for a machine by list index (wraps after 12)
 * @param {number} index - Position in the list
 * @returns {string} Icon URL
 */
function getMachineIconUrl(index) {
    return `/static/icons/machines/${MACHINE_ICONS[index % MACHINE_ICONS.length]}`;
}

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
        onItemAction: null,  // Display only for now
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
    // Sort alphabetically so icons are stable
    machines.sort((a, b) => a.id.localeCompare(b.id));
    return machines.map((m, index) => ({ ...m, iconUrl: getMachineIconUrl(index) }));
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
        <div class="machine-card">
            <div class="machine-icon-wrapper">
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
