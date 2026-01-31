# Voice Transcript Logs: Persistent Record of Spoken Interactions

> Searchable, timestamped logs of all voice interactions with STT confidence and audio replay.

## Problem

Voice commands vanish. Unlike typed commands that persist in terminal history, bash history, and session logs, spoken commands leave no trace:

```
# Typed command - retrievable forever
$ agentwire send -s myproject "Add authentication to the API"
# ↑ This is in bash_history, terminal scrollback, session logs

# Voice command - gone
[User says]: "Add authentication to the API"
# ↑ What exactly did I say? What did the STT hear? No record.
```

This creates real problems:

1. **Debugging STT errors**: "I said X but the agent did Y" - was it STT mishearing or agent misunderstanding?
2. **Session review**: Can't review what commands were given in a complex session
3. **Reproducibility**: Can't replay a successful workflow
4. **Learning**: Can't study effective voice command patterns
5. **Accountability**: In team settings, no audit trail of who said what

Voice is the primary interface. It deserves first-class logging.

## Why This Matters

Voice-first workflows break when you can't trust or verify the input chain:

```
[Day 1]
User: "Deploy to staging"
Agent: Deploys to production
User: "I said staging!"
Agent: "You said 'deploy to prod and staging'"
User: ...did I?

[Day 2]
User: Uses voice hesitantly, switches to typing for critical commands
```

Without transcript logs, users lose confidence in voice. They fall back to typing, defeating the purpose of a voice interface.

## Proposed Solution

### 1. Capture Every Voice Interaction

Log all STT transcriptions with metadata:

```yaml
# ~/.agentwire/transcripts/2024-01-15.jsonl
{"ts": "2024-01-15T10:30:00Z", "session": "myproject", "text": "Add JWT authentication", "confidence": 0.94, "audio_ref": "a1b2c3.webm", "duration_ms": 1850}
{"ts": "2024-01-15T10:30:45Z", "session": "myproject", "text": "Actually use session tokens instead", "confidence": 0.91, "audio_ref": "d4e5f6.webm", "duration_ms": 2100}
{"ts": "2024-01-15T10:31:30Z", "session": "myproject", "text": "Stop worker one", "confidence": 0.98, "audio_ref": "g7h8i9.webm", "duration_ms": 980, "was_interrupt": true}
```

### 2. Store Audio Clips

Keep the original audio for verification:

```
~/.agentwire/transcripts/audio/
├── 2024-01-15/
│   ├── a1b2c3.webm  # "Add JWT authentication"
│   ├── d4e5f6.webm  # "Actually use session tokens instead"
│   └── g7h8i9.webm  # "Stop worker one"
```

Audio enables:
- Re-transcription with different STT models
- Human review of disputed commands
- Training data for voice model improvement
- Playing back "what did I actually say?"

### 3. CLI Commands

```bash
# View recent transcripts
agentwire transcript list
agentwire transcript list --session myproject
agentwire transcript list --today

# Search transcripts
agentwire transcript search "deploy"
agentwire transcript search --low-confidence  # Find STT mistakes

# Play audio
agentwire transcript play a1b2c3
agentwire transcript play --last  # Play most recent

# Export for review
agentwire transcript export --session myproject --format markdown > session-review.md

# Annotate (mark STT errors for improvement)
agentwire transcript annotate a1b2c3 --correct "Add JWT authentication to the login endpoint"
```

### 4. Portal UI Integration

Add transcript panel to the portal:

```
┌─────────────────────────────────────────────────┐
│ Session: myproject                    [Monitor] │
├─────────────────────────────────────────────────┤
│                                                 │
│  [Terminal output here]                         │
│                                                 │
├─────────────────────────────────────────────────┤
│ Voice Transcript                    [▶] [🔍]    │
├─────────────────────────────────────────────────┤
│ 10:30:00  "Add JWT authentication"        94%   │
│ 10:30:45  "Actually use session tokens"   91%   │
│ 10:31:30  "Stop worker one" ⚡            98%   │
└─────────────────────────────────────────────────┘
```

Features:
- Click to play audio
- Confidence color coding (green >90%, yellow 80-90%, red <80%)
- Interrupt commands highlighted
- Filter by time range, confidence, session

### 5. Confidence Thresholds

Use confidence scores proactively:

```python
async def handle_voice(audio: bytes, session: str):
    result = await transcribe(audio)

    # Log regardless of confidence
    log_transcript(result)

    if result.confidence < 0.7:
        # Low confidence - ask for confirmation
        say(f"I heard '{result.text}', is that right?")
        confirmation = await listen_for_confirmation()
        if not confirmation:
            say("Please try again")
            return

    # Proceed with command
    await process_command(result.text, session)
```

### 6. Session Summaries

Generate voice activity summaries:

```bash
$ agentwire transcript summary --session myproject

Session: myproject (Jan 15, 2024)
Duration: 2h 15m
Voice commands: 47
  - Task instructions: 23
  - Interrupts: 8
  - Corrections: 6
  - Questions: 10

Low confidence moments: 3
  10:45:12 "deploy to prod" (heard as "deploy to Prague") - 67%
  11:20:33 "stop" (heard as "start") - 71%
  12:05:00 "roll back" (heard as "hold that") - 68%

Peak activity: 11:00-11:30 (15 commands)
```

## Implementation

### Transcript Logger

```python
@dataclass
class TranscriptEntry:
    timestamp: datetime
    session: str
    text: str
    confidence: float
    audio_ref: str | None
    duration_ms: int
    was_interrupt: bool = False
    corrected_text: str | None = None

class TranscriptLogger:
    def __init__(self, base_dir: Path = Path.home() / ".agentwire" / "transcripts"):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: TranscriptEntry):
        """Append transcript entry to daily log file."""
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        log_file = self.base_dir / f"{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(entry), default=str) + "\n")

    def save_audio(self, audio: bytes, ref: str, timestamp: datetime):
        """Save audio clip for later playback."""
        date_dir = self.base_dir / "audio" / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        audio_path = date_dir / f"{ref}.webm"
        audio_path.write_bytes(audio)

    def search(self, query: str, session: str | None = None) -> list[TranscriptEntry]:
        """Full-text search across transcripts."""
        results = []
        for log_file in self.base_dir.glob("*.jsonl"):
            with open(log_file) as f:
                for line in f:
                    entry = json.loads(line)
                    if query.lower() in entry["text"].lower():
                        if session is None or entry["session"] == session:
                            results.append(TranscriptEntry(**entry))
        return sorted(results, key=lambda e: e.timestamp, reverse=True)
```

### STT Integration

Modify the STT handler to log transcripts:

```python
logger = TranscriptLogger()

async def process_stt_result(audio: bytes, result: STTResult, session: str):
    # Generate audio reference
    audio_ref = hashlib.sha256(audio).hexdigest()[:12]

    # Detect if this was an interrupt command
    was_interrupt = detect_interrupt(result.text) is not None

    # Create transcript entry
    entry = TranscriptEntry(
        timestamp=datetime.now(UTC),
        session=session,
        text=result.text,
        confidence=result.confidence,
        audio_ref=audio_ref,
        duration_ms=len(audio) // 32,  # Approximate from WebM
        was_interrupt=was_interrupt
    )

    # Log transcript and save audio
    logger.log(entry)
    logger.save_audio(audio, audio_ref, entry.timestamp)

    return result
```

### Cleanup / Retention

```python
async def cleanup_old_transcripts(retention_days: int = 30):
    """Remove transcripts older than retention period."""
    cutoff = datetime.now() - timedelta(days=retention_days)

    for log_file in transcript_dir.glob("*.jsonl"):
        date_str = log_file.stem  # "2024-01-15"
        file_date = datetime.strptime(date_str, "%Y-%m-%d")
        if file_date < cutoff:
            log_file.unlink()

            # Remove corresponding audio
            audio_dir = transcript_dir / "audio" / date_str
            if audio_dir.exists():
                shutil.rmtree(audio_dir)
```

## Configuration

```yaml
# In ~/.agentwire/config.yaml
transcripts:
  enabled: true

  # What to store
  store_audio: true          # Keep original audio clips
  store_low_confidence: true # Log even low-confidence results

  # Retention
  retention_days: 30         # How long to keep transcripts
  audio_retention_days: 7    # Audio takes more space, shorter retention

  # Thresholds
  confidence_threshold: 0.7  # Below this, ask for confirmation

  # Storage location
  path: "~/.agentwire/transcripts"
```

## MCP Tools

```python
@mcp.tool()
def transcripts_list(
    session: str | None = None,
    date: str | None = None,
    limit: int = 20
) -> str:
    """List recent voice transcripts.

    Args:
        session: Filter by session name
        date: Filter by date (YYYY-MM-DD)
        limit: Max entries to return
    """

@mcp.tool()
def transcripts_search(
    query: str,
    session: str | None = None,
    low_confidence_only: bool = False
) -> str:
    """Search voice transcripts.

    Args:
        query: Text to search for
        session: Filter by session
        low_confidence_only: Only show STT mistakes (confidence < 80%)
    """

@mcp.tool()
def transcripts_play(audio_ref: str) -> str:
    """Play audio clip from transcript.

    Returns instructions for playing locally or streams to portal.
    """
```

## Privacy Considerations

Voice transcripts are sensitive. Handle carefully:

1. **Local storage only** - Transcripts stay on the machine, never uploaded
2. **Encrypted at rest** (optional) - For shared machines
3. **No team sync** - Unlike failure memory, transcripts don't propagate
4. **Easy deletion** - `agentwire transcript clear` removes everything
5. **Configurable audio** - Can disable audio storage, keep only text

```yaml
transcripts:
  store_audio: false  # Text only, no voice recordings
  encrypt: true       # Encrypt transcript logs
```

## Potential Challenges

1. **Storage growth**: Audio clips add up quickly.
   - Solution: Aggressive audio retention (7 days default), text stays longer

2. **Audio format compatibility**: Different browsers/devices send different formats.
   - Solution: Normalize to WebM/Opus on capture, or store original + metadata

3. **Multi-device sync**: User speaks from phone, wants to review on desktop.
   - Solution: Out of scope initially; transcripts are device-local

4. **Performance of search**: JSONL files don't scale to millions of entries.
   - Solution: SQLite for large installations, JSONL fine for personal use

5. **Privacy regulations**: In some jurisdictions, recording voice has legal requirements.
   - Solution: Opt-in, clear documentation, easy deletion

## Success Criteria

1. Users can answer "what did I actually say?" within seconds
2. STT errors are discoverable via low-confidence search
3. Session reviews include voice command history
4. Users trust voice more because they can verify transcription
5. Debugging voice issues becomes straightforward

## Non-Goals

- **Speech-to-speech translation** - We log, not translate
- **Voice biometrics** - We don't identify speakers
- **Real-time correction** - User can annotate later, not live edit
- **Cross-device sync** - Local-only for privacy
- **Training data export** - Not building STT training pipelines

## Future Extensions

### Transcript Replay

Play back a session's voice commands with timing:

```bash
agentwire transcript replay --session myproject --date 2024-01-15
# Plays audio clips in sequence with timestamps
```

Useful for demos, training, or "what happened yesterday?"

### STT Improvement Feedback Loop

Annotations (user corrections) could feed back to improve STT:

```bash
# User corrects an STT error
agentwire transcript annotate a1b2c3 --correct "deploy to staging"

# System learns from corrections
# Next time "staging" has higher prior probability
```

### Voice Command Statistics

Aggregate analysis of voice patterns:

```bash
agentwire transcript stats --last-30d

Most common commands:
  stop (142 times)
  spawn worker (89 times)
  actually... (67 times, high correction rate)

Average confidence: 0.91
Commands below 80% confidence: 12%

Peak usage hours: 10am-12pm, 3pm-5pm
```

### Integration with Session Replay

Link transcripts to session replay (from idea-session-replay.md):

```
Timeline view:
10:30:00 [Voice] "Add authentication"
10:30:02 [Agent] Reads auth.ts
10:30:15 [Agent] Writes jwt.ts
10:30:45 [Voice] "Actually use sessions"  ← click to hear
10:30:47 [Agent] Deletes jwt.ts
...
```

Voice and agent actions in unified timeline.
