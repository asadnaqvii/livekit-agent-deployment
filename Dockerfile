FROM python:3.10-slim

WORKDIR /app
COPY . .

# Install required system packages
RUN apt-get update && apt-get install -y ffmpeg build-essential git

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir livekit-agents fastapi uvicorn python-dotenv

# (Optional) Run any model file download step — keep only if needed
RUN python main.py download-files || echo "Skipping model download step."

# Optional: declare exposed port (not strictly required if no FastAPI)
EXPOSE 10000

# Run the LiveKit agent directly
CMD ["python", "main.py"]
