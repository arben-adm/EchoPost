FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx jinja2 python-multipart itsdangerous pydub

COPY main.py .
COPY templates/ templates/

ENV DB_PATH=/data/echopost.db
VOLUME ["/data"]

EXPOSE 3010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3010"]
