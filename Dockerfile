# Use the official slim Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install OS-level dependencies and clean up
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg \
      build-essential \
      git \
 && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (for better caching)
COPY requirements.txt .

# Upgrade pip and install Python deps
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      -r requirements.txt \
      livekit-plugins-deepgram>=1.0.0

# Copy the rest of your application code
COPY . .

# Pre‑download any model files or assets (as your old Dockerfile did)
RUN python main.py download-files

# Expose the port your agent listens on
EXPOSE 10000

# Launch your agent
CMD ["python", "main.py"]
