# Voice Identity: Multi-User Session Routing

> Identify speakers by voice and route commands to their respective sessions.

## Problem

AgentWire currently assumes a single user. In practice, multiple people might use the same endpoint:

- **Household**: Partner walks into office, says "what's the status?" - goes to wrong session
- **Team**: Multiple developers share a machine with different projects
- **Pair programming**: Two people working together, each with their own session
- **Accidental activation**: Someone else talks near the mic, triggers unintended commands

Current state: One push-to-talk → one session. No disambiguation.

This creates friction:
- **Session switching**: Must manually switch sessions before speaking
- **Cross-contamination**: Commands intended for one project go to another
- **No personalization**: Everyone gets the same voice, same preferences
- **Security risk**: No voice-based access control

## Proposed Solution

**Voice Identity** - speaker identification that routes commands to the correct session and applies user preferences.

### How It Works

```
┌─────────────────────────────────────────────────────┐
│                    Voice Input                       │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│              Speaker Identification                  │
│  ┌─────────────────────────────────────────────┐    │
│  │ Voice embedding → Match against profiles    │    │
│  │ "This sounds like User A (92% confidence)"  │    │
│  └─────────────────────────────────────────────┘    │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│                  Route to Session                    │
│  User A → project-alpha                             │
│  User B → project-beta                              │
│  Unknown → prompt for identification                │
└─────────────────────────────────────────────────────┘
```

### Voice Profile Enrollment

Users enroll their voice with a brief sample:

```bash
# Start enrollment
agentwire voice enroll start

# System prompts:
# "Please say: 'The quick brown fox jumps over the lazy dog'"
# "Now say: 'Pack my box with five dozen liquor jugs'"
# "Finally, say your name naturally a few times"

# Save profile
agentwire voice enroll finish --name "alice"
```

Enrollment captures:
- Voice embedding (speaker characteristics)
- Preferred name for greetings
- Default session (optional)
- Preferred TTS voice for responses

### User Configuration

```yaml
# ~/.agentwire/users.yaml
users:
  alice:
    voice_profile: ~/.agentwire/voices/alice.profile
    default_session: project-alpha
    response_voice: may
    permissions:
      - all

  bob:
    voice_profile: ~/.agentwire/voices/bob.profile
    default_session: project-beta
    response_voice: nova
    permissions:
      - read_only  # Can query status but not execute

  guest:
    # No profile - catch-all for unknown voices
    permissions:
      - status_only
    require_confirmation: true
```

### Routing Logic

```python
def route_command(audio: bytes) -> Session:
    # 1. Extract voice embedding
    embedding = extract_speaker_embedding(audio)

    # 2. Match against enrolled profiles
    matches = [(user, similarity(embedding, user.profile))
               for user in enrolled_users]

    best_match, confidence = max(matches, key=lambda x: x[1])

    # 3. Route based on confidence
    if confidence > 0.85:
        return get_session(best_match.default_session)
    elif confidence > 0.70:
        # Ask for confirmation
        speak(f"Is this {best_match.name}?")
        if await confirm():
            return get_session(best_match.default_session)
    else:
        # Unknown speaker
        return handle_unknown_speaker(audio)
```

### Session Greetings

When a recognized user speaks after a period of silence:

```
[Alice speaks]: "What's the status?"
[System]: "Hey Alice. Project Alpha has 2 workers running..."

[Bob speaks]: "Check the build"
[System]: "Hi Bob. Project Beta build passed 3 minutes ago."
```

Personalized greetings confirm routing worked correctly.

### Handoff Mode

For pair programming, explicitly share a session:

```
[Alice]: "Share this session with Bob"
[System]: "Session shared. Bob can now send commands here."

[Bob]: "Add a test for the login function"
[System]: (routes to Alice's session, not Bob's default)
```

### Security Permissions

Different users can have different permission levels:

| Permission | Description |
|------------|-------------|
| `all` | Full access - execute, modify, spawn workers |
| `execute` | Can run commands but not modify system config |
| `read_only` | Can query status but not execute |
| `status_only` | Can only ask "what's running?" type questions |
| `none` | Voice rejected, log only |

```yaml
# Guest access for unknown voices
guest:
  permissions: [status_only]
  require_confirmation: true
  notify_owner: true  # Alert registered users
```

### Voice Spoofing Protection

Basic anti-spoofing measures:

1. **Liveness detection**: Require random phrase during enrollment
2. **Playback detection**: Detect audio artifacts of recordings
3. **Confidence thresholds**: High threshold for sensitive operations
4. **Multi-factor option**: Voice + push-to-talk button = higher trust

```yaml
security:
  min_confidence: 0.85
  sensitive_ops_confidence: 0.95  # For destructive commands
  enable_liveness_check: true
  multi_factor:
    - voice
    - physical_button  # Optional hardware token
```

## Implementation Considerations

### Speaker Embedding Model

Use a pre-trained speaker verification model:

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| ECAPA-TDNN | 20MB | Fast | Good |
| WavLM + X-vector | 300MB | Medium | Better |
| Whisper embeddings | 0 (reuse STT) | Free | Okay |

Recommend: Start with Whisper embeddings (already loaded for STT), graduate to ECAPA-TDNN if accuracy insufficient.

### Embedding Extraction

```python
# Using speechbrain for ECAPA-TDNN
from speechbrain.pretrained import EncoderClassifier

classifier = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb"
)

def extract_embedding(audio_path: str) -> np.ndarray:
    signal = classifier.load_audio(audio_path)
    embedding = classifier.encode_batch(signal)
    return embedding.squeeze().numpy()

def similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
```

### Profile Storage

```
~/.agentwire/
├── users.yaml           # User configuration
└── voices/
    ├── alice.profile    # Numpy array + metadata
    ├── bob.profile
    └── samples/         # Enrollment audio (for re-training)
        ├── alice/
        └── bob/
```

Profile format:
```python
{
    "name": "alice",
    "embedding": np.array([...]),  # 192-dim or similar
    "enrolled_at": "2024-01-15T10:30:00Z",
    "samples_count": 5,
    "confidence_history": [0.92, 0.89, 0.94, ...]  # For quality tracking
}
```

### Latency Impact

Speaker identification adds processing time:

| Step | Time |
|------|------|
| Audio capture | 0ms (parallel) |
| Embedding extraction | 50-100ms |
| Profile matching | 5-10ms |
| **Total added latency** | **55-110ms** |

This runs parallel to STT, so effective latency increase is minimal.

### Confidence Degradation

Voice changes over time (illness, aging, microphone changes). Handle gracefully:

```python
def check_profile_health(user: User, recent_matches: list[float]):
    avg_confidence = sum(recent_matches[-10:]) / len(recent_matches[-10:])

    if avg_confidence < 0.80:
        speak(f"{user.name}, your voice profile may need updating. "
              f"Say 'update my voice' when convenient.")
```

### CLI Commands

```bash
# Enrollment
agentwire voice enroll start
agentwire voice enroll finish --name alice

# Management
agentwire voice list                    # List enrolled users
agentwire voice show alice              # Show profile details
agentwire voice update alice            # Re-enroll
agentwire voice delete alice            # Remove profile

# Testing
agentwire voice identify                # Record and identify
agentwire voice test alice              # Test against specific profile

# Permissions
agentwire voice permissions alice       # Show permissions
agentwire voice grant alice execute     # Add permission
agentwire voice revoke bob all          # Remove permission
```

### MCP Tools

```python
@mcp.tool()
def voice_identify() -> str:
    """Identify the current speaker from recent audio.

    Returns speaker name and confidence, or 'unknown'.
    """

@mcp.tool()
def voice_users_list() -> str:
    """List enrolled voice profiles with their default sessions."""

@mcp.tool()
def voice_share_session(with_user: str) -> str:
    """Share current session with another enrolled user."""
```

## Potential Challenges

1. **Similar voices**: Family members or people with similar vocal characteristics. Solution: Allow manual override, require confirmation for close matches.

2. **Voice changes**: Cold, age, emotional state affect voice. Solution: Adaptive learning from confirmed identifications, periodic re-enrollment prompts.

3. **Background voices**: TV, other people in room. Solution: Require push-to-talk activation first, then identify speaker during that window.

4. **Privacy concerns**: Storing voice biometrics. Solution: Store only embeddings (not reconstructible to audio), local-only by default, clear deletion path.

5. **Cold start**: New users must enroll before using. Solution: Guest mode with limited permissions, one-command quick enrollment.

6. **Multi-language**: Voice characteristics may vary by language spoken. Solution: Enroll in primary language, test cross-language accuracy.

## Example Day-in-the-Life

```
# Morning - Alice starts work
[Alice]: "Start the dev server"
[System]: "Good morning Alice. Starting dev server for project-alpha..."

# Bob joins
[Bob]: "What's the status?"
[System]: "Hey Bob. Project-beta has no active sessions. Want me to start one?"

# Unknown voice (visitor)
[Visitor]: "Run the tests"
[System]: "I don't recognize your voice. Alice, should I allow this?"
[Alice]: "Yes, just this once"
[System]: "Running tests..."

# Shared session
[Alice]: "Bob, join my session"
[System]: "Bob can now speak to project-alpha."
[Bob]: "Add error handling to the login form"
[System]: (executes in Alice's session)
```

## Success Metrics

- Speaker identification accuracy >90% for enrolled users
- Latency increase <150ms
- Zero unintended cross-session commands
- User satisfaction with personalized experience
- Reduced friction for multi-user households/teams
