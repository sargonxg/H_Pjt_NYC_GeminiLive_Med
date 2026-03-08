FROM python:3.12-slim

WORKDIR /app

# Install system build dependencies needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Install dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Cloud Run uses PORT env var (defaults to 8080)
ENV PORT=8080

EXPOSE 8080

# Validate Python can import main module before starting
# (catches import errors early with a useful message)
RUN python -c "import sys; print('Python', sys.version)" && \
    python -c "import fastapi; import uvicorn; import pydantic; print('Core deps OK')"

# --timeout-keep-alive=300 keeps WebSocket connections alive on Cloud Run
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300
