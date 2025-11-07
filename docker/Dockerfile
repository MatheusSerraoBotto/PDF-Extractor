# ==============================================================================
# Development Dockerfile for PDF Extraction API
# ==============================================================================
# This Dockerfile is optimized for local development with hot-reload and debugging
# ==============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for Docker layer caching)
COPY requirements.txt .
COPY requirements-dev.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy application code
COPY src/ /app/src/
COPY docker/start-api.sh /app/docker/start-api.sh

# Make startup script executable
RUN chmod +x /app/docker/start-api.sh

# Expose ports
EXPOSE 8000
EXPOSE 5678

# Use development startup script
CMD ["/app/docker/start-api.sh"]
