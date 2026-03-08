FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Cloud Run uses PORT env var (defaults to 8080)
ENV PORT=8080

EXPOSE 8080

# --timeout-keep-alive=300 keeps WebSocket connections alive on Cloud Run
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 300
