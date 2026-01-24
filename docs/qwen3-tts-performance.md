# Qwen3-TTS Performance Benchmarks

> Living document. Update this, don't create new versions.

## Hardware

- **GPU**: NVIDIA RTX 3080 (12GB VRAM)
- **Platform**: Ubuntu/WSL2 on dotdev-pc

## Model Variants

| Model | VRAM Usage | Notes |
|-------|------------|-------|
| Qwen3-TTS-12Hz-0.6B-Base | ~6.7GB | Faster, more consistent |
| Qwen3-TTS-12Hz-1.7B-Base | ~8.6GB | Higher quality, preferred |

## Backend Comparison (Jan 2026)

Test: `agentwire say "Hey there, let me tell you about this cool feature." -v <voice>`

| Backend | Time | Notes |
|---------|------|-------|
| **chatterbox** | ~6-8s | **Fastest**, recommended default |
| qwen-custom (streaming) | ~10-12s | Preset voices + emotion |
| qwen-custom (non-streaming) | ~15s | Preset voices + emotion |
| qwen-design | ~10-14s | Voice from description |
| qwen-base-1.7b | ~20s | Highest quality cloning |

**Recommendation:** Use `chatterbox` as default (~3x faster than qwen-base). Use qwen backends for voice design or when higher quality is needed.

## Qwen Model Performance Details

### 1.7B Model

| Configuration | Avg Time | Best | Worst | Notes |
|---------------|----------|------|-------|-------|
| Baseline (SDPA) | ~13s | 10.5s | 26s | High variance |
| + torch.compile (reduce-overhead) | ~10.5s | 8.7s | 12s | Good balance |
| + torch.compile (max-autotune) | ~13.8s | - | - | Worse for single requests |

### 0.6B Model

| Configuration | Avg Time | Best | Worst | Notes |
|---------------|----------|------|-------|-------|
| Baseline (SDPA) | ~11.6s | - | - | More consistent |

## Current Configuration

- Mode: `reduce-overhead` torch.compile
- Backend: SDPA (FlashAttention available but not providing speedup)
- GPU optimizations: cuDNN benchmark, TF32 matmul

## Venv Hot-Swap

Switching between venv families requires server restart:

| Switch | Action |
|--------|--------|
| qwen ↔ qwen | Hot-swap (no restart) |
| chatterbox ↔ chatterbox | Hot-swap (no restart) |
| qwen ↔ chatterbox | Auto-restart (~15-30s) |

## Potential Further Optimizations

| Option | Expected Gain | Effort | Notes |
|--------|---------------|--------|-------|
| vLLM-Omni | 2-5x | High | Recommended by Qwen team |
| Quantization (FP8/AWQ) | 30-50% | Medium | May impact quality |
| Streaming mode | Lower latency | Medium | First-packet faster |
| Dedicated inference server | Variable | High | Separate from API |

## References

- [Qwen3-TTS GitHub](https://github.com/QwenLM/Qwen3-TTS)
- [vLLM-Omni](https://github.com/vllm-project/vllm-omni)
