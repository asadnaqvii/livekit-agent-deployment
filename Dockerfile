FROM python:3.10-slim
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg build-essential git \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt livekit-plugins-deepgram>=1.0.0 \
 && pip install --no-cache-dir requests
 && pip install --no-cache-dir torch

COPY . .

# Download model files at build time so startup is faster
RUN python main.py download-files

EXPOSE 10000

# Run the worker at container startup—now you can inject LIVEKIT_API_KEY, etc.
CMD ["python", "main.py", "start"]
