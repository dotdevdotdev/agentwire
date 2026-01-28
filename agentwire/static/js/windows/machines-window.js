/**
 * Machines Window - displays all registered machines with status
 */

import { ListWindow } from '../list-window.js';
import { machineIcons } from '../icon-manager.js';
import { IconPicker } from '../components/icon-picker.js';
import { ListCard } from '../components/list-card.js';

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

    // Build meta - show "local" tag for local machines, id for remote if different from host
    const metaParts = [];
    if (machine.local) {
        metaParts.push(`<span class="type-tag type-local">local</span>`);
    } else if (machine.id !== machine.host) {
        metaParts.push(`<span class="session-path">${machine.id}</span>`);
    }

    return ListCard({
        id: machine.id,
        iconUrl: machine.iconUrl,
        statusOnline: isOnline,
        name: machine.host || machine.id,
        meta: metaParts.join(' · ')
        // No actions for machines
    });
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
