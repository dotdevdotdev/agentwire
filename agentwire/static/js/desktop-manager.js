/**
 * Desktop Manager - Singleton for managing the desktop environment.
 *
 * Provides:
 * - Single WebSocket connection shared by all windows
 * - Window registry for tracking open WinBox instances
 * - State management (sessions, machines, config)
 * - Event dispatching for state updates
 *
 * @module desktop-manager
 */

// Reconnect configuration
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const RECONNECT_MULTIPLIER = 1.5;

class DesktopManager {
    constructor() {
        /** @type {WebSocket|null} */
        this.ws = null;

        /** @type {Map<string, WinBox>} */
        this.windows = new Map();

        /** @type {Array<Object>} */
        this.sessions = [];

        /** @type {Array<Object>} */
        this.machines = [];

        /** @type {Object} */
        this.config = {};

        /** @type {Map<string, Set<Function>>} */
        this.listeners = new Map();

        /** @type {number} */
        this.reconnectAttempts = 0;

        /** @type {number|null} */
        this.reconnectTimeout = null;

        /** @type {boolean} */
        this.intentionalDisconnect = false;

        /** @type {string|null} */
        this.activeWindow = null;

        /** @type {AudioContext|null} */
        this._audioContext = null;
    }

    // ============================================
    // Lifecycle
    // ============================================

    /**
     * Connect to the WebSocket server.
     * @returns {Promise<void>}
     */
    async connect() {
        this.intentionalDisconnect = false;

        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws`;

        try {
            this.ws = new WebSocket(url);
        } catch (err) {
            console.error('[DesktopManager] Failed to create WebSocket:', err);
            this.scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            console.log('[DesktopManager] WebSocket connected');
            this.reconnectAttempts = 0;
            this.emit('connect');
        };

        this.ws.onclose = (event) => {
            console.log('[DesktopManager] WebSocket disconnected:', event.code, event.reason);
            this.ws = null;
            this.emit('disconnect');

            if (!this.intentionalDisconnect) {
                this.scheduleReconnect();
            }
        };

        this.ws.onerror = (error) => {
            console.error('[DesktopManager] WebSocket error:', error);
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event);
        };
    }

    /**
     * Disconnect from the WebSocket server.
     */
    disconnect() {
        this.intentionalDisconnect = true;

        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        this.reconnectAttempts = 0;
    }

    /**
     * Calculate reconnect delay with exponential backoff.
     * @returns {number} Delay in milliseconds
     */
    getReconnectDelay() {
        return Math.min(
            INITIAL_RECONNECT_DELAY * Math.pow(RECONNECT_MULTIPLIER, this.reconnectAttempts),
            MAX_RECONNECT_DELAY
        );
    }

    /**
     * Schedule a reconnection attempt.
     */
    scheduleReconnect() {
        if (this.intentionalDisconnect) return;

        const delay = this.getReconnectDelay();
        this.reconnectAttempts++;

        console.log(`[DesktopManager] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        this.reconnectTimeout = setTimeout(() => {
            this.reconnectTimeout = null;
            if (!this.intentionalDisconnect) {
                this.connect();
            }
        }, delay);
    }

    /**
     * Handle incoming WebSocket messages.
     * @param {MessageEvent} event
     */
    handleMessage(event) {
        let msg;
        try {
            msg = JSON.parse(event.data);
        } catch (err) {
            console.error('[DesktopManager] Failed to parse message:', err);
            return;
        }

        switch (msg.type) {
            case 'sessions_update':
                this.sessions = msg.sessions || [];
                this.emit('sessions', this.sessions);
                break;

            case 'machines_update':
                this.machines = msg.machines || [];
                this.emit('machines', this.machines);
                break;

            case 'config_update':
                this.config = msg.config || {};
                this.emit('config', this.config);
                break;

            case 'session_activity':
                this.emit('session_activity', {
                    session: msg.session,
                    active: msg.active
                });
                break;

            case 'session_created':
                this.emit('session_created', { session: msg.session });
                break;

            case 'session_closed':
                this.emit('session_closed', { session: msg.session });
                break;

            case 'pane_died':
                this.emit('pane_died', { session: msg.session, pane_id: msg.pane_id });
                break;

            case 'pane_created':
                this.emit('pane_created', { session: msg.session, pane_id: msg.pane_id });
                break;

            case 'tts_start':
                console.log('[DesktopManager] TTS starting for session:', msg.session);
                this.emit('tts_start', { session: msg.session, text: msg.text });
                break;

            case 'audio':
                console.log('[DesktopManager] Audio received for session:', msg.session, 'length:', msg.data?.length);
                this._playAudio(msg.data, msg.session);
                this.emit('audio', { session: msg.session });
                break;

            default:
                console.log('[DesktopManager] Unknown message type:', msg.type);
        }
    }

    // ============================================
    // Window Management
    // ============================================

    /** @type {number} Viewport width threshold for narrow mode */
    static NARROW_VIEWPORT_WIDTH = 600;

    /**
     * Check if we're on a narrow viewport (mobile/tablet).
     * @returns {boolean}
     */
    isNarrowViewport() {
        return window.innerWidth < DesktopManager.NARROW_VIEWPORT_WIDTH;
    }

    /**
     * Safely call a WinBox method, handling invalid states.
     * @param {WinBox} winbox - WinBox instance
     * @param {string} method - Method name ('minimize', 'maximize', 'focus')
     * @param {string} [windowId] - Window ID for logging/cleanup
     * @returns {boolean} True if successful, false if failed
     * @private
     */
    _safeWinBoxOp(winbox, method, windowId = null) {
        if (!winbox || !winbox.body || typeof winbox[method] !== 'function') {
            return false;
        }
        try {
            winbox[method]();
            return true;
        } catch (e) {
            console.warn(`[DesktopManager] Failed to ${method}${windowId ? ` ${windowId}` : ''}, removing from registry:`, e);
            if (windowId) {
                this.windows.delete(windowId);
            }
            return false;
        }
    }

    /**
     * Register a window with the manager.
     * On narrow viewports (< 600px), auto-minimizes other windows and maximizes the new one.
     * @param {string} id - Window identifier
     * @param {WinBox} winbox - WinBox instance
     */
    registerWindow(id, winbox) {
        this.windows.set(id, winbox);

        // On narrow viewports, use single-window mode: minimize others, maximize this one
        if (this.isNarrowViewport()) {
            this.minimizeAllExcept(id);
            if (winbox && !winbox.max) {
                this._safeWinBoxOp(winbox, 'maximize', id);
            }
        }

        this.emit('window_registered', { id, winbox });
    }

    /**
     * Minimize all windows except the specified one.
     * @param {string} exceptId - Window ID to keep open (optional)
     */
    minimizeAllExcept(exceptId = null) {
        for (const [windowId, winbox] of this.windows) {
            if (windowId !== exceptId && winbox && !winbox.min) {
                this._safeWinBoxOp(winbox, 'minimize', windowId);
            }
        }
    }

    /**
     * Unregister a window from the manager.
     * @param {string} id - Window identifier
     */
    unregisterWindow(id) {
        this.windows.delete(id);
        if (this.activeWindow === id) {
            this.activeWindow = null;
        }
        this.emit('window_unregistered', { id });
    }

    /**
     * Get a registered window by ID.
     * @param {string} id - Window identifier
     * @returns {WinBox|undefined}
     */
    getWindow(id) {
        return this.windows.get(id);
    }

    /**
     * Check if a window is registered.
     * @param {string} id - Window identifier
     * @returns {boolean}
     */
    hasWindow(id) {
        return this.windows.has(id);
    }

    /**
     * Get all registered windows.
     * @returns {Map<string, WinBox>}
     */
    getAllWindows() {
        return this.windows;
    }

    /**
     * Set the active window.
     * On narrow viewports, also maximizes the window and minimizes others.
     * @param {string|null} id - Window identifier
     */
    setActiveWindow(id) {
        this.activeWindow = id;

        // On narrow viewports, enforce single-window mode when a window gains focus
        if (id && this.isNarrowViewport()) {
            const winbox = this.windows.get(id);
            if (winbox) {
                this.minimizeAllExcept(id);
                if (!winbox.max) {
                    this._safeWinBoxOp(winbox, 'maximize', id);
                }
            }
        }

        this.emit('active_window_changed', { id });
    }

    /**
     * Get the active window ID.
     * @returns {string|null}
     */
    getActiveWindow() {
        return this.activeWindow;
    }

    // ============================================
    // Data Access
    // ============================================

    /**
     * Fetch sessions from the API.
     * @returns {Promise<Array<Object>>}
     */
    async fetchSessions() {
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

            this.sessions = allSessions;
            this.emit('sessions', this.sessions);
            return this.sessions;
        } catch (error) {
            console.error('[DesktopManager] Failed to fetch sessions:', error);
            return this.sessions;
        }
    }

    /**
     * Fetch machines from the API.
     * @returns {Promise<Array<Object>>}
     */
    async fetchMachines() {
        try {
            const response = await fetch('/api/machines');
            const data = await response.json();

            // API returns array directly, not {machines: [...]}
            this.machines = Array.isArray(data) ? data : (data.machines || []);
            this.emit('machines', this.machines);
            return this.machines;
        } catch (error) {
            console.error('[DesktopManager] Failed to fetch machines:', error);
            return this.machines;
        }
    }

    /**
     * Fetch config from the API.
     * @returns {Promise<Object>}
     */
    async fetchConfig() {
        try {
            const response = await fetch('/api/config');
            const data = await response.json();

            this.config = data || {};
            this.emit('config', this.config);
            return this.config;
        } catch (error) {
            console.error('[DesktopManager] Failed to fetch config:', error);
            return this.config;
        }
    }

    /**
     * Get cached sessions.
     * @returns {Array<Object>}
     */
    getSessions() {
        return this.sessions;
    }

    /**
     * Get cached machines.
     * @returns {Array<Object>}
     */
    getMachines() {
        return this.machines;
    }

    /**
     * Get cached config.
     * @returns {Object}
     */
    getConfig() {
        return this.config;
    }

    /**
     * Find a session by name.
     * @param {string} name - Session name
     * @returns {Object|undefined}
     */
    getSession(name) {
        return this.sessions.find(s => s.name === name);
    }

    /**
     * Find a machine by ID.
     * @param {string} id - Machine ID
     * @returns {Object|undefined}
     */
    getMachine(id) {
        return this.machines.find(m => m.id === id);
    }

    // ============================================
    // WebSocket Communication
    // ============================================

    /**
     * Send a message through the WebSocket.
     * @param {string} type - Message type
     * @param {Object} data - Message data
     * @returns {boolean} True if sent successfully
     */
    send(type, data = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('[DesktopManager] Cannot send - not connected');
            return false;
        }

        try {
            this.ws.send(JSON.stringify({ type, ...data }));
            return true;
        } catch (err) {
            console.error('[DesktopManager] Send failed:', err);
            return false;
        }
    }

    /**
     * Check if WebSocket is connected.
     * @returns {boolean}
     */
    isConnected() {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }

    // ============================================
    // Event System
    // ============================================

    /**
     * Subscribe to an event.
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);

        // Return unsubscribe function
        return () => this.off(event, callback);
    }

    /**
     * Unsubscribe from an event.
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    off(event, callback) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.delete(callback);
        }
    }

    /**
     * Emit an event to all subscribers.
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (err) {
                    console.error(`[DesktopManager] Error in ${event} handler:`, err);
                }
            });
        }
    }

    // ============================================
    // Audio Playback
    // ============================================

    /**
     * Play base64-encoded audio data.
     * @param {string} base64Data - Base64 encoded audio (WAV format)
     * @param {string} session - Session name for event emission
     */
    async _playAudio(base64Data, session) {
        if (!base64Data) {
            console.warn('[DesktopManager] No audio data to play');
            return;
        }

        try {
            // Decode base64 to binary
            const binaryString = atob(base64Data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Create or resume AudioContext
            if (!this._audioContext) {
                this._audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (this._audioContext.state === 'suspended') {
                await this._audioContext.resume();
            }

            // Decode and play
            const audioBuffer = await this._audioContext.decodeAudioData(bytes.buffer.slice(0));
            const source = this._audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this._audioContext.destination);

            // Emit audio_ended when playback finishes
            source.onended = () => {
                console.log('[DesktopManager] Audio playback ended for session:', session);
                this.emit('audio_ended', { session });
            };

            source.start(0);

            console.log('[DesktopManager] Audio playback started, duration:', audioBuffer.duration.toFixed(2), 's');
        } catch (err) {
            console.error('[DesktopManager] Audio playback failed:', err);
        }
    }
}

// Export singleton instance
export const desktop = new DesktopManager();
