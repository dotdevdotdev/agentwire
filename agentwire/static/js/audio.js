/**
 * Audio handling module for AgentWire session.
 *
 * Provides push-to-talk recording, TTS playback, and device selection.
 *
 * @module audio
 */

// ============================================
// State
// ============================================

/** @type {MediaRecorder|null} */
let mediaRecorder = null;

/** @type {Blob[]} */
let audioChunks = [];

/** @type {MediaStream|null} */
let recordingStream = null;

/** @type {HTMLAudioElement|null} */
let currentAudio = null;

/** @type {string} */
let inputDeviceId = '';

/** @type {string} */
let outputDeviceId = '';

/** @type {Function|null} */
let onRecordingCompleteCallback = null;

// Audio level monitoring
/** @type {AudioContext|null} */
let monitorContext = null;

/** @type {AnalyserNode|null} */
let monitorAnalyser = null;

/** @type {MediaStream|null} */
let monitorStream = null;

/** @type {number|null} */
let levelInterval = null;

/** @type {Function|null} */
let onLevelChangeCallback = null;

// Storage keys
const STORAGE_KEY_INPUT = 'agentwire-mic-id';
const STORAGE_KEY_OUTPUT = 'agentwire-speaker-id';

// ============================================
// Initialization
// ============================================

/**
 * Initialize the audio recorder.
 *
 * @param {Function} onRecordingComplete - Callback when recording stops, receives Blob
 * @param {Function} [onLevelChange] - Optional callback for audio level updates (0-100)
 */
export function initRecorder(onRecordingComplete, onLevelChange = null) {
    onRecordingCompleteCallback = onRecordingComplete;
    onLevelChangeCallback = onLevelChange;

    // Load saved device preferences
    inputDeviceId = localStorage.getItem(STORAGE_KEY_INPUT) || '';
    outputDeviceId = localStorage.getItem(STORAGE_KEY_OUTPUT) || '';
}

// ============================================
// Recording
// ============================================

/**
 * Start recording audio from the microphone.
 * Uses push-to-talk pattern - call stopRecording() when done.
 *
 * @returns {Promise<boolean>} True if recording started successfully
 */
export async function startRecording() {
    // Stop any existing recording
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }

    try {
        const constraints = {
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        };

        if (inputDeviceId) {
            constraints.audio.deviceId = { exact: inputDeviceId };
        }

        recordingStream = await navigator.mediaDevices.getUserMedia(constraints);
        audioChunks = [];

        mediaRecorder = new MediaRecorder(recordingStream, {
            mimeType: 'audio/webm'
        });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            // Stop all tracks
            if (recordingStream) {
                recordingStream.getTracks().forEach(track => track.stop());
                recordingStream = null;
            }

            // Stop level monitoring
            stopLevelMonitor();

            // Create blob and call callback
            if (audioChunks.length > 0 && onRecordingCompleteCallback) {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                onRecordingCompleteCallback(audioBlob);
            }

            audioChunks = [];
        };

        // Start recording with timeslice for progressive data
        mediaRecorder.start(100);

        // Start level monitoring if callback provided
        if (onLevelChangeCallback) {
            await startLevelMonitor();
        }

        return true;

    } catch (err) {
        console.error('[Audio] Failed to start recording:', err);
        return false;
    }
}

/**
 * Stop recording and trigger the onRecordingComplete callback.
 * Includes a small delay to capture final audio.
 */
export function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state !== 'recording') {
        return;
    }

    // Small delay to ensure we capture the end of speech
    setTimeout(() => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
    }, 200);
}

/**
 * Check if currently recording.
 * @returns {boolean} True if recording is in progress
 */
export function isRecording() {
    return mediaRecorder !== null && mediaRecorder.state === 'recording';
}

// ============================================
// Level Monitoring
// ============================================

/**
 * Start monitoring audio input levels.
 * @private
 */
async function startLevelMonitor() {
    try {
        const constraints = {
            audio: inputDeviceId ? { deviceId: { exact: inputDeviceId } } : true
        };

        monitorStream = await navigator.mediaDevices.getUserMedia(constraints);
        monitorContext = new AudioContext();
        monitorAnalyser = monitorContext.createAnalyser();

        const source = monitorContext.createMediaStreamSource(monitorStream);
        source.connect(monitorAnalyser);
        monitorAnalyser.fftSize = 256;

        const dataArray = new Uint8Array(monitorAnalyser.frequencyBinCount);

        levelInterval = setInterval(() => {
            if (monitorAnalyser && onLevelChangeCallback) {
                monitorAnalyser.getByteFrequencyData(dataArray);
                const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
                const level = Math.min(100, avg * 2);
                onLevelChangeCallback(level);
            }
        }, 50);

    } catch (err) {
        console.log('[Audio] Level monitor not available:', err);
    }
}

/**
 * Stop monitoring audio input levels.
 * @private
 */
function stopLevelMonitor() {
    if (levelInterval) {
        clearInterval(levelInterval);
        levelInterval = null;
    }

    if (monitorStream) {
        monitorStream.getTracks().forEach(track => track.stop());
        monitorStream = null;
    }

    if (monitorContext) {
        monitorContext.close();
        monitorContext = null;
    }

    monitorAnalyser = null;

    // Reset level to 0
    if (onLevelChangeCallback) {
        onLevelChangeCallback(0);
    }
}

// ============================================
// TTS Playback
// ============================================

/**
 * Play TTS audio from base64-encoded WAV data.
 *
 * @param {string} base64Data - Base64-encoded WAV audio
 * @returns {Promise<void>} Resolves when audio finishes playing
 */
export async function playTts(base64Data) {
    // Stop any currently playing audio
    stopTts();

    return new Promise((resolve, reject) => {
        const audio = new Audio('data:audio/wav;base64,' + base64Data);
        currentAudio = audio;

        // Set output device if supported and configured
        if (outputDeviceId && 'setSinkId' in audio) {
            audio.setSinkId(outputDeviceId).catch(err => {
                console.log('[Audio] Could not set speaker:', err);
            });
        }

        audio.onended = () => {
            if (currentAudio === audio) {
                currentAudio = null;
            }
            resolve();
        };

        audio.onerror = (err) => {
            console.error('[Audio] Playback error:', err);
            if (currentAudio === audio) {
                currentAudio = null;
            }
            reject(err);
        };

        audio.play().catch(err => {
            console.error('[Audio] Play failed:', err);
            if (currentAudio === audio) {
                currentAudio = null;
            }
            reject(err);
        });
    });
}

/**
 * Stop any currently playing TTS audio.
 */
export function stopTts() {
    if (currentAudio) {
        currentAudio.onended = null;  // Prevent callback
        currentAudio.pause();
        currentAudio = null;
    }
}

/**
 * Check if TTS audio is currently playing.
 * @returns {boolean} True if audio is playing
 */
export function isPlaying() {
    return currentAudio !== null && !currentAudio.paused;
}

// ============================================
// Device Selection
// ============================================

/**
 * Set the audio input device (microphone).
 *
 * @param {string} deviceId - The device ID to use, or empty string for default
 */
export function setInputDevice(deviceId) {
    inputDeviceId = deviceId;
    localStorage.setItem(STORAGE_KEY_INPUT, deviceId);
}

/**
 * Set the audio output device (speaker).
 *
 * @param {string} deviceId - The device ID to use, or empty string for default
 */
export function setOutputDevice(deviceId) {
    outputDeviceId = deviceId;
    localStorage.setItem(STORAGE_KEY_OUTPUT, deviceId);
}

/**
 * Get the current input device ID.
 * @returns {string} The device ID or empty string for default
 */
export function getInputDevice() {
    return inputDeviceId;
}

/**
 * Get the current output device ID.
 * @returns {string} The device ID or empty string for default
 */
export function getOutputDevice() {
    return outputDeviceId;
}

/**
 * Enumerate available audio devices.
 *
 * @returns {Promise<{inputs: MediaDeviceInfo[], outputs: MediaDeviceInfo[]}>}
 *          Object containing arrays of input and output devices
 */
export async function enumerateDevices() {
    try {
        // Request permission first to get labeled devices
        await navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => stream.getTracks().forEach(t => t.stop()));

        const devices = await navigator.mediaDevices.enumerateDevices();

        return {
            inputs: devices.filter(d => d.kind === 'audioinput'),
            outputs: devices.filter(d => d.kind === 'audiooutput')
        };
    } catch (err) {
        console.error('[Audio] Could not enumerate devices:', err);
        return { inputs: [], outputs: [] };
    }
}

/**
 * Check if output device selection is supported.
 * This is only available in Chrome and Edge.
 *
 * @returns {boolean} True if setSinkId is supported
 */
export function isOutputSelectionSupported() {
    return 'setSinkId' in HTMLAudioElement.prototype;
}
