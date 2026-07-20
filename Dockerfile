FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies if any are needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first to leverage Docker cache
COPY backend/requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY backend/ ./backend/

# Copy source data files so the pipeline can find them at runtime
COPY data/ ./data/

# Create data directories and set permissions so Hugging Face user can write to them
RUN mkdir -p /app/data/sources && chmod -R 777 /app/data

# Set PYTHONPATH so Python can locate our backend module
ENV PYTHONPATH=/app

# Port: 7860 is the Hugging Face Spaces convention and matches this repo's
# README frontmatter (app_port: 7860), which is where HF routes external
# traffic. HF also injects a PORT env var at runtime; honor it if present,
# fall back to 7860 otherwise. (Previously the Dockerfile hardcoded 8081
# while the README declared 7860 -- HF forwarded to 7860 where nothing
# listened, so the Space was unreachable. Reconciled on 7860.)
ENV PORT=7860
EXPOSE 7860

# Shell form so ${PORT} expands. uvicorn binds whatever HF provides.
CMD uvicorn backend.api:app --host 0.0.0.0 --port ${PORT}
