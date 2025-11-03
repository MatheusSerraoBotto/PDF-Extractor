# ===============================
#  Base Dockerfile for PDF Extraction AI
#  ------------------------------------
#  This image defines the runtime environment for the FastAPI + LangChain app.
#  It installs system dependencies, Python packages, and prepares the service.
# ===============================

# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install essential system dependencies (PDF tools, build utils)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (to leverage Docker layer caching)
COPY ../requirements.txt .
COPY ../requirements-dev.txt .

# Install production and development dependencies
RUN pip install --no-cache-dir -r requirements.txt 
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy the entire project
COPY . .

# Set default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=development \
    LANGCHAIN_CACHE=redis \
    LLM_PROVIDER=langchain \
    LOG_LEVEL=INFO

# Expose API port
EXPOSE 8000

# Default command (runs FastAPI app via Uvicorn)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
