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

EXPOSE 8081

CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8081"]
