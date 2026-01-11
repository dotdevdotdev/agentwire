/**
 * WebSocket handling module for AgentWire session connections.
 *
 * Provides connection management with auto-reconnect and exponential backoff.
 *
 * @module websocket
 */

/** @type {WebSocket|null} */
let ws = null;

/** @type {string|null} */
let sessionName = null;

/** @type {Object|null} */
let handlers = null;

/** @type {number} */
let reconnectAttempts = 0;

/** @type {number|null} */
let reconnectTimeout = null;

/** @type {boolean} */
let intentionalDisconnect = false;

// Reconnect configuration
const INITIAL_RECONNECT_DELAY = 1000;  // 1 second
const MAX_RECONNECT_DELAY = 30000;     // 30 seconds
const RECONNECT_MULTIPLIER = 1.5;

/**
 * Calculate reconnect delay with exponential backoff.
 * @returns {number} Delay in milliseconds
 */
function getReconnectDelay() {
    const delay = Math.min(
        INITIAL_RECONNECT_DELAY * Math.pow(RECONNECT_MULTIPLIER, reconnectAttempts),
        MAX_RECONNECT_DELAY
    );
    return delay;
}

/**
 * Connect to the WebSocket server for a specific session.
 *
 * @param {string} session - The session name to connect to
 * @param {Object} eventHandlers - Handlers for various message types
 * @param {Function} [eventHandlers.onOutput] - Called when terminal output is received
 * @param {Function} [eventHandlers.onTts] - Called when TTS data is received (tts_start, audio)
 * @param {Function} [eventHandlers.onAsk] - Called when a question or permission request is received
 * @param {Function} [eventHandlers.onState] - Called when session state changes (locked/unlocked)
 * @param {Function} [eventHandlers.onConnect] - Called when connection is established
 * @param {Function} [eventHandlers.onDisconnect] - Called when connection is lost
 * @param {Function} [eventHandlers.onActivity] - Called when session activity is detected (session-specific)
 * @param {Function} [eventHandlers.onSessionActivity] - Called when any session's activity changes (dashboard global updates)
 */
export function connect(session, eventHandlers) {
    sessionName = session;
    handlers = eventHandlers || {};
    intentionalDisconnect = false;

    // Clear any pending reconnect
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }

    // Close existing connection if any
    if (ws) {
        ws.close();
        ws = null;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws/${sessionName}`;

    try {
        ws = new WebSocket(url);
    } catch (err) {
        console.error('[WebSocket] Failed to create connection:', err);
        scheduleReconnect();
        return;
    }

    ws.onopen = () => {
        console.log('[WebSocket] Connected to', sessionName);
        reconnectAttempts = 0;  // Reset backoff on successful connection

        if (handlers.onConnect) {
            handlers.onConnect();
        }
    };

    ws.onclose = (event) => {
        console.log('[WebSocket] Disconnected:', event.code, event.reason);
        ws = null;

        if (handlers.onDisconnect) {
            handlers.onDisconnect();
        }

        // Auto-reconnect unless intentionally disconnected
        if (!intentionalDisconnect) {
            scheduleReconnect();
        }
    };

    ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        // Note: onclose will be called after onerror, so reconnect is handled there
    };

    ws.onmessage = (event) => {
        let msg;
        try {
            msg = JSON.parse(event.data);
        } catch (err) {
            console.error('[WebSocket] Failed to parse message:', err);
            return;
        }

        handleMessage(msg);
    };
}

/**
 * Route incoming messages to appropriate handlers.
 * @param {Object} msg - The parsed message object
 */
function handleMessage(msg) {
    switch (msg.type) {
        case 'output':
            if (handlers.onOutput) {
                handlers.onOutput(msg.data);
            }
            break;

        case 'activity':
            if (handlers.onActivity) {
                handlers.onActivity();
            }
            break;

        case 'session_activity':
            if (handlers.onSessionActivity) {
                handlers.onSessionActivity({
                    session: msg.session,
                    active: msg.active
                });
            }
            break;

        case 'tts_start':
            if (handlers.onTts) {
                handlers.onTts('start', { text: msg.text });
            }
            break;

        case 'audio':
            if (handlers.onTts) {
                handlers.onTts('audio', { data: msg.data });
            }
            break;

        case 'question':
            if (handlers.onAsk) {
                handlers.onAsk('question', {
                    header: msg.header,
                    question: msg.question,
                    options: msg.options
                });
            }
            break;

        case 'question_answered':
            if (handlers.onAsk) {
                handlers.onAsk('question_answered', {});
            }
            break;

        case 'permission_request':
            if (handlers.onAsk) {
                handlers.onAsk('permission_request', {
                    toolName: msg.tool_name,
                    toolInput: msg.tool_input,
                    message: msg.message
                });
            }
            break;

        case 'permission_resolved':
            if (handlers.onAsk) {
                handlers.onAsk('permission_resolved', {});
            }
            break;

        case 'session_locked':
            if (handlers.onState) {
                handlers.onState('locked');
            }
            break;

        case 'session_unlocked':
            if (handlers.onState) {
                handlers.onState('unlocked');
            }
            break;

        default:
            console.log('[WebSocket] Unknown message type:', msg.type);
    }
}

/**
 * Schedule a reconnection attempt with exponential backoff.
 */
function scheduleReconnect() {
    if (intentionalDisconnect) {
        return;
    }

    const delay = getReconnectDelay();
    reconnectAttempts++;

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);

    reconnectTimeout = setTimeout(() => {
        reconnectTimeout = null;
        if (sessionName && !intentionalDisconnect) {
            connect(sessionName, handlers);
        }
    }, delay);
}

/**
 * Send a message through the WebSocket connection.
 *
 * @param {string} type - The message type
 * @param {Object} [data] - Additional data to send
 * @returns {boolean} True if message was sent, false if connection is not open
 */
export function send(type, data = {}) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn('[WebSocket] Cannot send - not connected');
        return false;
    }

    const message = { type, ...data };

    try {
        ws.send(JSON.stringify(message));
        return true;
    } catch (err) {
        console.error('[WebSocket] Send failed:', err);
        return false;
    }
}

/**
 * Disconnect from the WebSocket server.
 * This is an intentional disconnect that will not trigger auto-reconnect.
 */
export function disconnect() {
    intentionalDisconnect = true;

    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }

    if (ws) {
        ws.close();
        ws = null;
    }

    sessionName = null;
    handlers = null;
    reconnectAttempts = 0;
}

/**
 * Check if the WebSocket is currently connected.
 * @returns {boolean} True if connected
 */
export function isConnected() {
    return ws !== null && ws.readyState === WebSocket.OPEN;
}

/**
 * Get the current session name.
 * @returns {string|null} The session name or null if not connected
 */
export function getRoom() {
    return sessionName;
}
