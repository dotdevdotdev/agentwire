/**
 * IconManager - Smart icon assignment with persistence
 *
 * Features:
 * - Name matching: item name matches icon filename → auto-assign
 * - Random assignment: no duplicates within a list
 * - localStorage persistence: icons stay consistent across refreshes
 * - User override: manual icon selection
 */

// Available icons per category
const ICON_SETS = {
    sessions: [
        'agentwire.jpeg', 'android.jpeg', 'bear.jpeg', 'cat.jpeg', 'crown.jpeg',
        'cyborg.jpeg', 'deer.jpeg', 'drone.jpeg', 'eagle.jpeg', 'fox.jpeg',
        'hawk.jpeg', 'horse.jpeg', 'lion.jpeg', 'mech.jpeg', 'microphone.jpeg',
        'owl.jpeg', 'rabbit.jpeg', 'robot.jpeg', 'tiger.jpeg', 'wolf.jpeg'
    ],
    machines: [
        'android.jpeg', 'automaton.jpeg', 'bot.jpeg', 'cyborg.jpeg', 'droid.jpeg',
        'drone.jpeg', 'guardian.jpeg', 'mech.jpeg', 'probe.jpeg', 'robot.jpeg',
        'sentinel.jpeg', 'unit.jpeg'
    ],
    projects: [
        'blob.jpeg', 'cloud.jpeg', 'crystal.jpeg', 'cyclops.jpeg', 'flame.jpeg',
        'fuzzy.jpeg', 'horned.jpeg', 'moon.jpeg', 'slime.jpeg', 'star.jpeg',
        'tentacle.jpeg', 'winged.jpeg'
    ]
};

/**
 * IconManager handles icon assignment for a specific category
 */
export class IconManager {
    /**
     * @param {'sessions'|'machines'|'projects'} type - Category type
     */
    constructor(type) {
        this.type = type;
        this.storageKey = `agentwire_icons_${type}`;
        this.availableIcons = ICON_SETS[type] || [];
        this.basePath = `/static/icons/${type}/`;
    }

    /**
     * Load saved icon assignments from localStorage
     * @returns {Object} Map of itemName → iconFilename
     */
    loadAssignments() {
        try {
            const data = localStorage.getItem(this.storageKey);
            if (data) {
                return JSON.parse(data);
            }
        } catch (e) {
            console.warn(`[IconManager] Failed to load ${this.type} assignments:`, e);
        }
        return {};
    }

    /**
     * Save icon assignments to localStorage
     * @param {Object} assignments - Map of itemName → iconFilename
     */
    saveAssignments(assignments) {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(assignments));
        } catch (e) {
            console.warn(`[IconManager] Failed to save ${this.type} assignments:`, e);
        }
    }

    /**
     * Get icon URL for a single item
     * @param {string} itemName - Item name
     * @returns {string} Icon URL
     */
    getIcon(itemName) {
        const assignments = this.loadAssignments();

        // Check saved assignment
        if (assignments[itemName] && this.availableIcons.includes(assignments[itemName])) {
            return this.basePath + assignments[itemName];
        }

        // Check name match
        const nameMatch = this._findNameMatch(itemName);
        if (nameMatch) {
            assignments[itemName] = nameMatch;
            this.saveAssignments(assignments);
            return this.basePath + nameMatch;
        }

        // Random assignment (may have duplicates when called individually)
        const randomIcon = this._getRandomIcon(Object.values(assignments));
        assignments[itemName] = randomIcon;
        this.saveAssignments(assignments);
        return this.basePath + randomIcon;
    }

    /**
     * Get icons for a list of items (ensures no duplicates within the list)
     * @param {string[]} itemNames - Array of item names
     * @returns {Object} Map of itemName → iconUrl
     */
    getIconsForItems(itemNames) {
        const assignments = this.loadAssignments();
        const result = {};
        const usedIcons = new Set();

        // First pass: use saved assignments and name matches
        for (const name of itemNames) {
            // Check saved assignment
            if (assignments[name] && this.availableIcons.includes(assignments[name])) {
                result[name] = this.basePath + assignments[name];
                usedIcons.add(assignments[name]);
                continue;
            }

            // Check name match
            const nameMatch = this._findNameMatch(name);
            if (nameMatch && !usedIcons.has(nameMatch)) {
                assignments[name] = nameMatch;
                result[name] = this.basePath + nameMatch;
                usedIcons.add(nameMatch);
            }
        }

        // Second pass: random assignment for remaining items
        for (const name of itemNames) {
            if (result[name]) continue;

            const randomIcon = this._getRandomIcon(usedIcons);
            assignments[name] = randomIcon;
            result[name] = this.basePath + randomIcon;
            usedIcons.add(randomIcon);
        }

        // Save updated assignments
        this.saveAssignments(assignments);

        return result;
    }

    /**
     * Set icon for an item (user override)
     * @param {string} itemName - Item name
     * @param {string} iconFilename - Icon filename (e.g., 'fox.jpeg')
     */
    setIcon(itemName, iconFilename) {
        if (!this.availableIcons.includes(iconFilename)) {
            console.warn(`[IconManager] Invalid icon: ${iconFilename}`);
            return;
        }

        const assignments = this.loadAssignments();
        assignments[itemName] = iconFilename;
        this.saveAssignments(assignments);
    }

    /**
     * Get available icons for picker UI
     * @param {string} currentItem - Currently selected item (to highlight its icon)
     * @returns {Array} Array of { filename, url, isAssigned }
     */
    getAvailableIcons(currentItem = null) {
        const assignments = this.loadAssignments();
        const currentIcon = assignments[currentItem];

        return this.availableIcons.map(filename => ({
            filename,
            url: this.basePath + filename,
            isAssigned: filename === currentIcon
        }));
    }

    /**
     * Clear all assignments (reset to default)
     */
    clearAssignments() {
        localStorage.removeItem(this.storageKey);
    }

    /**
     * Find an icon that matches the item name
     * @param {string} itemName - Item name to match
     * @returns {string|null} Matching icon filename or null
     */
    _findNameMatch(itemName) {
        const normalizedName = itemName.toLowerCase().replace(/[^a-z0-9]/g, '');

        for (const icon of this.availableIcons) {
            const iconName = icon.replace(/\.[^.]+$/, '').toLowerCase();
            if (iconName === normalizedName) {
                return icon;
            }
        }
        return null;
    }

    /**
     * Get a random icon, preferring unused ones
     * @param {Set|Array} usedIcons - Icons already in use
     * @returns {string} Icon filename
     */
    _getRandomIcon(usedIcons) {
        const usedSet = usedIcons instanceof Set ? usedIcons : new Set(usedIcons);

        // Find unused icons
        const unused = this.availableIcons.filter(icon => !usedSet.has(icon));

        if (unused.length > 0) {
            // Random from unused
            return unused[Math.floor(Math.random() * unused.length)];
        }

        // All icons used, pick random (allows duplicates for large lists)
        return this.availableIcons[Math.floor(Math.random() * this.availableIcons.length)];
    }
}

// Singleton instances for each category
export const sessionIcons = new IconManager('sessions');
export const machineIcons = new IconManager('machines');
export const projectIcons = new IconManager('projects');
