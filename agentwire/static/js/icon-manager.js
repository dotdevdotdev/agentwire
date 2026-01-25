/**
 * IconManager - Smart icon assignment with persistence
 *
 * Features:
 * - Dynamic icon discovery: fetches available icons from server
 * - Name matching: item name matches icon filename → auto-assign
 * - Random assignment: no duplicates within a list
 * - localStorage persistence: icons stay consistent across refreshes
 * - User override: manual icon selection
 */

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
        this.availableIcons = [];
        this.basePath = `/static/icons/${type}/`;
        this._iconsLoaded = false;
        this._loadPromise = null;
    }

    /**
     * Fetch available icons from server (cached after first call)
     * @returns {Promise<string[]>} Array of icon filenames
     */
    async fetchIcons() {
        if (this._iconsLoaded) {
            return this.availableIcons;
        }

        // Prevent multiple concurrent fetches
        if (this._loadPromise) {
            return this._loadPromise;
        }

        this._loadPromise = (async () => {
            try {
                const response = await fetch(`/api/icons/${this.type}`);
                if (response.ok) {
                    this.availableIcons = await response.json();
                }
            } catch (e) {
                console.warn(`[IconManager] Failed to fetch ${this.type} icons:`, e);
            }
            this._iconsLoaded = true;
            this._loadPromise = null;
            return this.availableIcons;
        })();

        return this._loadPromise;
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
     * @returns {Promise<string>} Icon URL
     */
    async getIcon(itemName) {
        await this.fetchIcons();
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
     * @returns {Promise<Object>} Map of itemName → iconUrl
     */
    async getIconsForItems(itemNames) {
        await this.fetchIcons();
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
     * @returns {Promise<Array>} Array of { filename, url, isAssigned }
     */
    async getAvailableIcons(currentItem = null) {
        await this.fetchIcons();
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
     * Force reload icons from server on next fetch
     */
    invalidateCache() {
        this._iconsLoaded = false;
        this._loadPromise = null;
    }

    /**
     * Find an icon that matches the item name
     * @param {string} itemName - Item name to match
     * @returns {string|null} Matching icon filename or null
     */
    _findNameMatch(itemName) {
        // Strip @machine suffix for remote sessions (e.g., "agentwire-tts@dotdev-pc" → "agentwire-tts")
        const baseName = itemName.split('@')[0];
        // Normalize: lowercase, remove non-alphanumeric (hyphens, etc.)
        const normalizedName = baseName.toLowerCase().replace(/[^a-z0-9]/g, '');

        for (const icon of this.availableIcons) {
            // Same normalization for icon filename
            const iconName = icon.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9]/g, '');
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
