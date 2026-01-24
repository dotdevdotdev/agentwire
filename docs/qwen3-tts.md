# Qwen3-TTS Complete Guide

> Living document. Update this, don't create new versions.

Qwen3-TTS is an open-source TTS model from Alibaba's Qwen team, released January 2026. Trained on 5+ million hours of speech data across 10 languages.

## Model Variants

| Model | Size | VRAM | Use Case |
|-------|------|------|----------|
| `Qwen3-TTS-12Hz-1.7B-Base` | 1.7B | ~8.6GB | Voice cloning from reference audio |
| `Qwen3-TTS-12Hz-0.6B-Base` | 0.6B | ~6.7GB | Lighter voice cloning |
| `Qwen3-TTS-12Hz-1.7B-VoiceDesign` | 1.7B | ~8.6GB | Generate voices from text descriptions |
| `Qwen3-TTS-12Hz-1.7B-CustomVoice` | 1.7B | ~8.6GB | 9 preset premium voices with emotion control |
| `Qwen3-TTS-12Hz-0.6B-CustomVoice` | 0.6B | ~6.7GB | Lighter preset voices |

**Currently deployed:** `Qwen3-TTS-12Hz-1.7B-Base` (voice cloning mode)

## Supported Languages

Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian

## API Methods

### 1. Voice Cloning (Base Models)

Clone any voice from a ~3-10 second reference audio:

```python
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", ...)

# Basic voice clone
wavs, sr = model.generate_voice_clone(
    text="Hello, this is a test.",
    language="English",
    ref_audio="path/to/voice.wav",
    ref_text="Optional transcript of reference",  # Improves prosody
    x_vector_only_mode=True,  # Speaker embedding only (no transcript needed)
)

# Reusable clone prompt (efficient for multiple generations)
prompt = model.create_voice_clone_prompt(
    ref_audio="path/to/voice.wav",
    ref_text="Optional transcript",
    x_vector_only_mode=False,
)

wavs, sr = model.generate_voice_clone(
    text=["Line 1", "Line 2", "Line 3"],
    language=["English", "English", "English"],
    voice_clone_prompt=prompt,  # Reuse without re-extracting
)
```

**Parameters:**
- `ref_audio`: File path, URL, numpy array, or (array, sample_rate) tuple
- `ref_text`: Transcript of reference (improves prosody matching)
- `x_vector_only_mode`: Use speaker embedding only (faster, no transcript needed)
- `voice_clone_prompt`: Pre-computed prompt for efficiency

### 2. Voice Design (VoiceDesign Model)

Generate voices from natural language descriptions:

```python
model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", ...)

wavs, sr = model.generate_voice_design(
    text="Your text to speak",
    language="English",
    instruct="Deep male voice with warm tone, speaking slowly and deliberately",
)
```

**Example Instructions:**

| Goal | Instruct |
|------|----------|
| Deep male narrator | "Deep male voice with gravelly undertones, speaks with authority" |
| Young excited female | "High-pitched young female voice, excited and energetic" |
| Calm meditation guide | "Soft, soothing female voice, speaks slowly with gentle pauses" |
| Angry character | "Speak in an angry, frustrated tone with rising intensity" |
| Sad/emotional | "Melancholic voice, speaks slowly with a hint of tears" |
| News anchor | "Professional, clear enunciation, neutral tone, moderate pace" |

**Controllable Attributes:**
- Timbre: deep, bright, husky, mellow, edgy
- Pitch: high, low, varied
- Emotion: happy, sad, angry, excited, calm, fearful
- Pace: slow, fast, varied rhythm
- Age: young, mature, elderly
- Gender: male, female
- Style: professional, casual, dramatic, soothing

### 3. Custom Voice (CustomVoice Model)

Use preset premium voices with optional emotion/style instructions:

```python
model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", ...)

wavs, sr = model.generate_custom_voice(
    text="Hello, how are you today?",
    language="English",
    speaker="Ryan",
    instruct="Very happy and enthusiastic",  # Optional emotion
)
```

**Preset Speakers:**

| Speaker | Description | Native Language |
|---------|-------------|-----------------|
| Vivian | Bright, slightly edgy young female | Chinese |
| Serena | Warm, gentle young female | Chinese |
| Uncle_Fu | Seasoned male, low mellow timbre | Chinese |
| Dylan | Youthful Beijing male, clear natural | Chinese (Beijing) |
| Eric | Lively Chengdu male, husky bright | Chinese (Sichuan) |
| Ryan | Dynamic male, strong rhythm | English |
| Aiden | Sunny American male, clear midrange | English |
| Ono_Anna | Playful Japanese female, light nimble | Japanese |
| Sohee | Warm Korean female, rich emotion | Korean |

All speakers can speak any of the 10 supported languages.

## Streaming Support

All models support streaming for low-latency applications (~97ms first packet):

```python
# Enable streaming
wavs, sr = model.generate_voice_clone(
    text="...",
    non_streaming_mode=False,  # Enable streaming
    ...
)
```

## Advanced: Design → Clone Workflow

Create a persistent character voice by combining VoiceDesign and Clone:

```python
# 1. Generate reference audio with VoiceDesign
design_model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", ...)
ref_wavs, sr = design_model.generate_voice_design(
    text="Hello, my name is Alex and I'm here to help you.",
    language="English",
    instruct="Young male tech enthusiast, friendly and approachable, clear voice",
)
soundfile.write("alex_reference.wav", ref_wavs[0], sr)

# 2. Create reusable clone prompt from that reference
clone_model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", ...)
alex_prompt = clone_model.create_voice_clone_prompt(
    ref_audio="alex_reference.wav",
    x_vector_only_mode=True,
)

# 3. Use the prompt for all future "Alex" lines
wavs, sr = clone_model.generate_voice_clone(
    text=["Line 1", "Line 2", "Line 3"],
    language=["English", "English", "English"],
    voice_clone_prompt=alex_prompt,
)
```

## Generation Parameters

Additional kwargs passed to HuggingFace generate:

```python
wavs, sr = model.generate_voice_clone(
    text="...",
    max_new_tokens=2048,  # Limit output length
    top_p=0.9,            # Nucleus sampling
    temperature=1.0,      # Sampling temperature
    ...
)
```

## Limitations vs Chatterbox

| Feature | Qwen3-TTS | Chatterbox |
|---------|-----------|------------|
| Voice cloning | ✓ (3s min) | ✓ |
| Paralinguistic tags (`[laugh]`, `[sigh]`, `[gasp]`) | ✗ | ✓ |
| Emotion control (Base/clone) | ✗ | ✗ |
| Emotion control (preset voices) | ✓ (CustomVoice) | ✗ |
| Voice design from text | ✓ (VoiceDesign) | ✗ |
| Multi-language | 10 languages | English only |
| Voice quality | Higher | Good |
| Speed (RTX 3080) | ~10s | ~5s |

**Bottom line:** Qwen3-TTS has better quality and more features, but lacks Chatterbox's paralinguistic tags for non-verbal sounds.

## Best Practices

### Voice Cloning
- Use 10-30 seconds of clean audio (not just the 3s minimum)
- Minimize background noise in reference
- Provide accurate transcript via `ref_text` for better prosody
- Use `x_vector_only_mode=True` if transcript is unavailable

### Voice Design
- Be specific: "Deep male voice with slight rasp" > "male voice"
- Include emotion: "speaks with excitement and energy"
- Mention pace: "slow and deliberate" or "quick and energetic"
- Describe persona: "wise elderly storyteller"

### Performance
- Use `x_vector_only_mode=True` for faster voice cloning
- Create `voice_clone_prompt` once, reuse for multiple generations
- 1.7B models have stronger emotion control than 0.6B
- torch.compile with `reduce-overhead` helps inference speed

## Integration with AgentWire

All Qwen3-TTS models are now integrated via the modular TTS architecture with hot-swap support.

### Available Backends

| Backend | Engine | Use Case |
|---------|--------|----------|
| `chatterbox` | Chatterbox Turbo | **Default** - fastest (~6s), paralinguistic tags |
| `qwen-base-0.6b` | Qwen3-TTS 0.6B Base | Lighter voice cloning |
| `qwen-base-1.7b` | Qwen3-TTS 1.7B Base | Higher quality voice cloning (~20s) |
| `qwen-design` | Qwen3-TTS VoiceDesign | Design voices from text descriptions (~10s) |
| `qwen-custom` | Qwen3-TTS CustomVoice | Preset voices with emotion control |

### CLI Usage

```bash
# Default (chatterbox) - fastest
agentwire say "Hello world" -v dotdev

# Voice cloning with qwen (higher quality)
agentwire say "Hello" --backend qwen-base-1.7b -v myvoice

# Design a new voice
agentwire say "Test this voice" --backend qwen-design --instruct "description"

# Preset voice with emotion
agentwire say "I am excited!" --backend qwen-custom -v Ryan --instruct "very enthusiastic"

# Paralinguistic tags (chatterbox only)
agentwire say "Ha! [laugh] That is funny [sigh]" -v jeremy
```

### Venv Hot-Swap

Chatterbox and Qwen require different Python dependencies. The system automatically handles this:

- **Same venv family** → hot-swap (no restart)
  - `qwen-base-0.6b` ↔ `qwen-base-1.7b` ↔ `qwen-design` ↔ `qwen-custom`
  - `chatterbox` ↔ `chatterbox-streaming`
- **Different venv family** → auto-restart server with correct venv
  - `chatterbox` ↔ any qwen backend

### Voice Design Workflow

Create persistent character voices:

```bash
# 1. Experiment with voice descriptions
agentwire say "Test phrase" --backend qwen-design --instruct "Young woman, Brooklyn accent, confident"

# 2. When you like one, generate a longer reference (via API)
curl -X POST http://localhost:8100/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Intro text for the voice...", "backend": "qwen-design", "instruct": "your description"}' \
  -o /tmp/newvoice.wav

# 3. Upload as voice clone
curl -X POST http://localhost:8100/voices/newvoice -F "file=@/tmp/newvoice.wav"

# 4. Use with any cloning backend
agentwire say "Hello" --backend chatterbox -v newvoice
agentwire say "Hello" --backend qwen-base-1.7b -v newvoice
```

### Voice Design Prompts That Work Well

| Voice Type | Instruct |
|------------|----------|
| Tech enthusiast woman | "Young woman with naturally high-pitched voice, speaks with rising intonation at end of phrases, friendly and enthusiastic but natural, slight vocal fry, American accent" |
| Sarcastic Southern guy | "Laid-back young man, dry sarcastic tone, slightly bored, deadpan delivery with subtle humor, New Orleans accent, Southern drawl" |
| Brooklyn woman | "Young woman in her twenties, Brooklyn New York accent, confident and flirty, streetwise attitude, slightly husky voice" |
| Latina cop | "Young Latina woman, slight Spanish accent, authoritative but warm, professional cop demeanor, clear and direct speech" |
| Soothing doctor | "Middle-aged woman, soothing and calming voice, trained speaker with strong downward inflections, soft quick asides between emphasized statements, warm and reassuring, gentle but controlled delivery" |
| British wizard | "Old British man, raspy weathered voice, wise wizard, mysterious and knowing, speaks slowly with gravitas, hints of gravel in throat" |
| California surfer | "Young man in his twenties, deep male voice, California surfer accent, slow relaxed speech, elongated vowels, Jeff Spicoli vibes" |

**Tips:**
- Specify gender and age explicitly ("young man", "middle-aged woman")
- Include accent details ("Brooklyn", "New Orleans", "British")
- Describe delivery style ("deadpan", "enthusiastic", "soothing")
- Mention speech patterns ("rising intonation", "downward inflections", "slow and deliberate")

### Performance Benchmarks (RTX 3080)

| Backend | Voice Type | Time |
|---------|------------|------|
| chatterbox | voice clone | ~6-8s |
| qwen-custom | preset + emotion | ~10-12s |
| qwen-design | from description | ~10-14s |
| qwen-base-1.7b | voice clone | ~20s |

**Recommendation:** Use `chatterbox` as default for speed. Use `qwen-design` for creating new voices, then clone them for daily use with `chatterbox`.

## Resources

- [GitHub - QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [HuggingFace Collection](https://huggingface.co/collections/Qwen/qwen3-tts)
- [Technical Report (arXiv:2601.15621)](https://arxiv.org/html/2601.15621v1)
- [Voice Design Demo](https://huggingface.co/spaces/Qwen/Qwen3-TTS-Voice-Design)
