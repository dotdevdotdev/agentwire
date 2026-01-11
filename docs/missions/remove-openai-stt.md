# Mission: Remove OpenAI STT Backend

Remove the OpenAI Whisper API STT backend since we have our own STT options.

## Context

AgentWire originally supported OpenAI's Whisper API as an STT option. We now have:
- `whisperkit` - macOS local (Apple Neural Engine)
- `whispercpp` - Local whisper.cpp
- `remote` - Connects to STT server (agentwire-stt Docker or local stt_server.py)
- `agentwire/stt/stt_server.py` - Our own faster-whisper server

The OpenAI backend is redundant and requires an external API key.

**Keep:**
- `agentwire/stt/remote.py` - Remote STT backend
- `agentwire/stt/stt_server.py` - Our faster-whisper server
- All whisperkit/whispercpp backends

**Remove:**
- `agentwire/stt/openai.py` - OpenAI Whisper API
- All `OPENAI_API_KEY` references

## Wave 1: Remove OpenAI STT Backend

**Task 1.1: Delete OpenAI STT module**
- Delete `agentwire/stt/openai.py`

**Task 1.2: Update STT __init__.py**
- Remove `OpenAISTT` import and from `__all__`
- Remove `openai` case from `get_stt_backend()`

**Task 1.3: Update default STT backend for Linux**
- File: `agentwire/config.py`
- Change `_default_stt_backend()`: return `"remote"` for Linux instead of `"openai"`

**Task 1.4: Update onboarding wizard**
- File: `agentwire/onboarding.py`
- Remove `("openai", "OpenAI API...")` from STT choices
- Remove OpenAI validation in `_validate_stt_backend()`
- Remove OpenAI hints in `_get_stt_setup_hints()`

**Task 1.5: Update example configs**
- `examples/config.yaml`: Remove openai from comments
- `examples/config-docker.yaml`: Change to `backend: "remote"` with `url: "http://stt:8100"`

**Task 1.6: Update documentation**
- `README.md`: Remove OpenAI STT references
- `docs/configuration.md`: Remove OPENAI_API_KEY docs
- `docs/TROUBLESHOOTING.md`: Remove OpenAI STT troubleshooting
- `docs/deployment.md`: Update Docker STT config to use remote

**Task 1.7: Update tests**
- Check for OpenAI STT test references

## Completion Criteria

- [ ] `agentwire/stt/openai.py` deleted
- [ ] No `openai` case in `get_stt_backend()`
- [ ] Default STT for Linux is `remote`
- [ ] Onboarding wizard doesn't offer OpenAI option
- [ ] No `OPENAI_API_KEY` references in active code/docs
- [ ] Docker example uses `remote` backend with stt service URL
- [ ] `agentwire/stt/remote.py` and `stt_server.py` untouched
