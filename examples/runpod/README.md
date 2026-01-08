# RunPod TTS Examples

Example scripts for testing and using AgentWire TTS on RunPod serverless infrastructure.

## Prerequisites

All scripts require environment variables:

```bash
export RUNPOD_API_KEY=your_api_key_here
export RUNPOD_ENDPOINT_ID=your_endpoint_id_here
```

Or create a `.env` file in the project root:

```bash
RUNPOD_API_KEY=your_api_key_here
RUNPOD_ENDPOINT_ID=your_endpoint_id_here
```

## Scripts

### Network Volume Management

| Script | Purpose |
|--------|---------|
| `upload_bashbunni.py` | Upload bashbunni voice to network volume and test it |
| `test_tiny_tina.py` | Upload tiny-tina voice to network volume and test it |
| `test_network_volume.py` | Comprehensive test of network volume functionality (upload, list, generate) |

### Performance Testing

| Script | Purpose |
|--------|---------|
| `test_runpod_audio.py` | Test TTS response times (cold start vs warm worker) with different text lengths |
| `test_cold_start.py` | Measure cold start performance |
| `test_default_voice.py` | Test default voice (no voice clone) |

### Edge Cases & Validation

| Script | Purpose |
|--------|---------|
| `test_edge_cases.py` | Test edge cases (empty text, very long text, special characters, unicode, numbers) |
| `test_runpod_serverless.py` | Basic serverless endpoint test |
| `check_endpoint_status.py` | Check RunPod endpoint health and status |

## Usage Examples

### Upload a Voice

```bash
# Upload bashbunni voice to network volume
uv run --script upload_bashbunni.py
```

### Test Network Volume

```bash
# Run comprehensive network volume tests
uv run --script test_network_volume.py
```

### Performance Testing

```bash
# Test response times with different text lengths
uv run --script test_runpod_audio.py
```

### Edge Case Testing

```bash
# Test edge cases and error handling
uv run --script test_edge_cases.py
```

## Network Volume Setup

1. Create a network volume in RunPod dashboard
2. Attach it to your serverless endpoint (auto-mounts at `/runpod-volume/`)
3. Upload voices using `upload_bashbunni.py` or `test_tiny_tina.py`
4. Voices persist across worker cold starts

## Voice Files

Test scripts expect voice files in:
- `~/.agentwire/voices_backup/` - Backup directory with voice samples

Voice files needed:
- `bashbunni.wav` (4.7 MB)
- `tiny-tina.wav` (208 KB)
- `dotdev.wav` (bundled in Docker image)

## Output

All scripts generate test audio files:
- `test_*.wav` - Generated TTS audio samples
- Files are excluded from git via `.gitignore`

## Notes

- All scripts use `uv run --script` for dependency management
- Dependencies are declared inline in script headers
- No hardcoded API keys - all use environment variables
- Scripts use `/runsync` endpoint for synchronous execution
