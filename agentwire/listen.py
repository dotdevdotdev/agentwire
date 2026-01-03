"""Voice input: record, transcribe, send to session."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from agentwire.agents.tmux import tmux_session_exists

CONFIG_DIR = Path.home() / ".agentwire"
LOCK_FILE = Path("/tmp/agentwire-listen.lock")
PID_FILE = Path("/tmp/agentwire-listen.pid")
AUDIO_FILE = Path("/tmp/agentwire-listen.wav")
DEBUG_LOG = Path("/tmp/agentwire-listen.log")


def log(msg: str) -> None:
    """Log debug message."""
    with open(DEBUG_LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {msg}\n")


def notify(msg: str) -> None:
    """Show system notification (non-blocking)."""
    if sys.platform == "darwin":
        subprocess.Popen([
            "osascript", "-e",
            f'display notification "{msg}" with title "AgentWire"'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def beep(sound: str) -> None:
    """Play system sound (non-blocking)."""
    if sys.platform == "darwin":
        sounds = {
            "start": "/System/Library/Sounds/Blow.aiff",
            "stop": "/System/Library/Sounds/Pop.aiff",
            "done": "/System/Library/Sounds/Glass.aiff",
            "error": "/System/Library/Sounds/Basso.aiff",
        }
        if sound in sounds:
            subprocess.Popen(["afplay", sounds[sound]],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def load_config() -> dict:
    """Load agentwire config."""
    config_path = CONFIG_DIR / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def get_whisperkit_model_path() -> str:
    """Get WhisperKit model path from config or default."""
    config = load_config()
    model_path = config.get("stt", {}).get("model_path")
    if model_path:
        return str(Path(model_path).expanduser())

    # Default macOS WhisperKit path
    default = Path.home() / "Library/Application Support/MacWhisper/models/whisperkit/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930"
    if default.exists():
        return str(default)

    return ""


def get_audio_device() -> str:
    """Get audio input device from config. Returns device index for ffmpeg."""
    config = load_config()
    # audio.input_device can be an integer index or "default"
    device = config.get("audio", {}).get("input_device", "default")
    if device == "default":
        return "default"
    return str(device)


def start_recording() -> int:
    """Start recording audio."""
    log("start_recording called")

    # Clean up any stale recording
    subprocess.run(["pkill", "-9", "-f", "ffmpeg.*agentwire-listen"],
                   capture_output=True)
    LOCK_FILE.unlink(missing_ok=True)
    PID_FILE.unlink(missing_ok=True)
    AUDIO_FILE.unlink(missing_ok=True)
    time.sleep(0.1)

    LOCK_FILE.touch()
    beep("start")

    # Record audio (16kHz mono for whisper)
    device = get_audio_device()

    if sys.platform == "darwin":
        # Build input specifier: ":N" for specific device, or ":default"
        if device == "default":
            input_spec = ":default"
        else:
            input_spec = f":{device}"

        proc = subprocess.Popen(
            ["ffmpeg", "-f", "avfoundation", "-i", input_spec,
             "-ar", "16000", "-ac", "1",
             "-acodec", "pcm_s16le",  # Uncompressed for quality
             str(AUDIO_FILE), "-y"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        # Linux - use pulse or alsa
        proc = subprocess.Popen(
            ["ffmpeg", "-f", "pulse", "-i", "default",
             "-ar", "16000", "-ac", "1",
             "-acodec", "pcm_s16le",
             str(AUDIO_FILE), "-y"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    PID_FILE.write_text(str(proc.pid))
    log(f"Started ffmpeg with PID {proc.pid}")
    print("Recording...")
    return 0


def stop_recording(session: str, voice_prompt: bool = True) -> int:
    """Stop recording, transcribe, and send to session."""
    log("stop_recording called")

    if not LOCK_FILE.exists():
        log("ERROR: No lock file")
        print("Not recording")
        beep("error")
        return 1

    beep("stop")
    log("Stopping ffmpeg")

    # Stop ffmpeg
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError):
            pass
        PID_FILE.unlink(missing_ok=True)

    subprocess.run(["pkill", "-9", "-f", "ffmpeg.*agentwire-listen"],
                   capture_output=True)
    LOCK_FILE.unlink(missing_ok=True)

    # Wait for file to be written
    time.sleep(0.3)

    if not AUDIO_FILE.exists():
        log("ERROR: No audio file")
        notify("Recording failed")
        beep("error")
        return 1

    log("Transcribing...")
    notify("Transcribing...")

    # Get config
    config = load_config()
    stt_backend = config.get("stt", {}).get("backend", "whisperkit")

    # Transcribe based on backend
    text = ""
    if stt_backend == "whisperkit":
        model_path = get_whisperkit_model_path()
        if not model_path:
            log("ERROR: No WhisperKit model path")
            notify("WhisperKit model not found")
            beep("error")
            return 1

        result = subprocess.run(
            ["whisperkit-cli", "transcribe",
             "--audio-path", str(AUDIO_FILE),
             "--model-path", model_path,
             "--language", "en",
             "--skip-special-tokens"],
            capture_output=True, text=True,
        )
        text = result.stdout.strip()

    elif stt_backend == "openai":
        # Use OpenAI Whisper API
        import urllib.request
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            log("ERROR: No OPENAI_API_KEY")
            notify("OPENAI_API_KEY not set")
            beep("error")
            return 1

        # TODO: Implement OpenAI API call
        notify("OpenAI STT not yet implemented")
        beep("error")
        return 1

    else:
        log(f"ERROR: Unknown STT backend: {stt_backend}")
        notify(f"Unknown STT backend: {stt_backend}")
        beep("error")
        return 1

    if not text:
        log("ERROR: No speech detected")
        notify("No speech detected")
        beep("error")
        AUDIO_FILE.unlink(missing_ok=True)
        return 1

    log(f"Transcribed: {text}")

    # Check if session exists
    if not tmux_session_exists(session):
        log(f"ERROR: No session '{session}'")
        notify(f"No session: {session}")
        beep("error")
        print(f"Transcribed: {text}")
        print(f"But session '{session}' not running. Start with: agentwire dev")
        AUDIO_FILE.unlink(missing_ok=True)
        return 1

    # Build message
    if voice_prompt:
        full_text = f"[Voice input - respond with say command] {text}"
    else:
        full_text = text

    log(f"Sending to session: {session}")

    # Use paste-buffer for reliable submission
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(full_text)
        tmpfile = f.name

    subprocess.run(["tmux", "load-buffer", tmpfile], check=True)
    Path(tmpfile).unlink()
    subprocess.run(["tmux", "paste-buffer", "-t", session], check=True)
    time.sleep(0.2)
    subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True)
    time.sleep(0.1)
    subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True)

    beep("done")
    log("SUCCESS: Sent to session")
    notify(f"Sent: {text[:30]}...")
    print(f"Sent to {session}: {text}")

    AUDIO_FILE.unlink(missing_ok=True)
    return 0


def cancel_recording() -> int:
    """Cancel current recording."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError):
            pass
        PID_FILE.unlink(missing_ok=True)

    subprocess.run(["pkill", "-9", "-f", "ffmpeg.*agentwire-listen"],
                   capture_output=True)
    LOCK_FILE.unlink(missing_ok=True)
    AUDIO_FILE.unlink(missing_ok=True)

    beep("error")
    notify("Cancelled")
    print("Cancelled")
    return 0


def is_recording() -> bool:
    """Check if currently recording."""
    return LOCK_FILE.exists()
