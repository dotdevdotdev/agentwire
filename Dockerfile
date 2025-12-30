# AgentWire Portal Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    openssh-client \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY agentwire/ agentwire/
COPY skills/ skills/

# Create config directory
RUN mkdir -p /root/.agentwire

# Default environment
ENV AGENTWIRE_SERVER__HOST=0.0.0.0
ENV AGENTWIRE_SERVER__PORT=8765

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -fsk https://localhost:8765/health || exit 1

# Run portal
CMD ["python", "-m", "agentwire", "portal", "serve"]
