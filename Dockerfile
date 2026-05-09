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

# Create data directories and set permissions so Hugging Face user can write to them
RUN mkdir -p /app/backend/data/sources && chmod -R 777 /app/backend/data

# Set PYTHONPATH so Python can locate our backend module
ENV PYTHONPATH=/app

# Expose Hugging Face Spaces default port
EXPOSE 7860

# Run uvicorn on port 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
