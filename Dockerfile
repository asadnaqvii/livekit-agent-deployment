FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y ffmpeg build-essential git
RUN pip install --no-cache-dir -U pip

# Install core + OpenAI & Cartesia plugins
RUN pip install --no-cache-dir "livekit-agents[openai,cartesia]>=1.0.0" \
    fastapi uvicorn python-dotenv
RUN pip install --no-cache-dir livekit-plugins-deepgram>=1.0.0

# Download any model files or assets
RUN python main.py download-files

EXPOSE 10000
CMD ["python", "healthcheck.py"]
