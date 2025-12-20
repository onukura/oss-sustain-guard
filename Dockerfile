# OSS Sustain Guard GitHub Action Docker Image
# Optimized for fast action execution with minimal dependencies

FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy only necessary files
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY oss_sustain_guard ./oss_sustain_guard

# Install Python dependencies with uv
RUN uv sync --no-dev --frozen

# Create entrypoint script
COPY action-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
