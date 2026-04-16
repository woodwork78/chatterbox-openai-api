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

# chatterbox-streaming pins torch==2.6.x; that build does not ship CUDA kernels for
# Blackwell (sm_120). Upgrade to the same line proven on RTX 50xx in production stacks.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
RUN pip install --upgrade pip \
    && pip install . \
    && pip install --upgrade torch==2.7.0 torchaudio==2.7.0 --index-url "${TORCH_INDEX_URL}"

EXPOSE 4123

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4123"]
