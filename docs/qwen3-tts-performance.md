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

## Baseline Performance (Jan 2026)

Test: `agentwire say -v dotdev "Testing message with one sentence."`

### 1.7B Model (Preferred)

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
