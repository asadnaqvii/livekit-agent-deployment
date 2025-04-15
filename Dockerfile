FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y ffmpeg build-essential git
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir livekit-agents fastapi uvicorn python-dotenv

# Download any model files or assets
RUN python main.py download-files

EXPOSE 10000
CMD ["python", "healthcheck.py"]
