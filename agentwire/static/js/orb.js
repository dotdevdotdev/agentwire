/**
 * Orb Component - State management for animated orb indicator
 *
 * States: idle, listening, processing, generating, speaking, locked, awaiting_permission
 */

// State configuration with labels
const stateConfig = {
    idle: { label: 'Ready' },
    listening: { label: 'Listening' },
    processing: { label: 'Processing' },
    generating: { label: 'Generating' },
    speaking: { label: 'Speaking' },
    locked: { label: 'Busy' },
    awaiting_permission: { label: 'Awaiting Permission' }
};

// Current state
let currentState = 'idle';

// Element references
let orbElement = null;
let ringElement = null;
let labelElement = null;

/**
 * Initialize the orb component with DOM element references
 * @param {HTMLElement} orb - The orb element
 * @param {HTMLElement} ring - The orb ring element
 * @param {HTMLElement} label - The state label element
 */
export function init(orb, ring, label) {
    orbElement = orb;
    ringElement = ring;
    labelElement = label;

    // Set initial state
    setOrbState('idle');
}

/**
 * Set the orb state
 * @param {string} state - One of: idle, listening, processing, generating, speaking, locked, awaiting_permission
 */
export function setOrbState(state) {
    if (!stateConfig[state]) {
        console.warn(`Unknown orb state: ${state}`);
        return;
    }

    currentState = state;
    const config = stateConfig[state];

    if (orbElement) {
        orbElement.className = 'orb ' + state;
    }

    if (ringElement) {
        ringElement.className = 'orb-ring ' + state;
    }

    if (labelElement) {
        labelElement.className = 'state-label ' + state;
        labelElement.textContent = config.label;
    }
}

/**
 * Get the current orb state
 * @returns {string} Current state
 */
export function getState() {
    return currentState;
}

/**
 * Check if orb is in a specific state
 * @param {string} state - State to check
 * @returns {boolean}
 */
export function isState(state) {
    return currentState === state;
}
