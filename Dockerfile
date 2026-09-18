FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# Install Korean fonts and system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fonts-nanum \
    fontconfig \
    curl \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure storage directory exists
RUN mkdir -p storage

EXPOSE 8000

# Coolify / Production start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
