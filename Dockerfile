FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY app ./app
COPY voices ./voices
COPY voice-registry.example.json ./

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 4123

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4123"]
