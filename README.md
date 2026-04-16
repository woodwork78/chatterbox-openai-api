# chatterbox-openai-api

`chatterbox-openai-api` is a Docker-first FastAPI wrapper that exposes local Chatterbox TTS through an OpenAI-compatible HTTP API.

It exists to bridge a practical gap:

- OpenAI-compatible community wrappers often buffer full synthesis before returning audio.
- `davidbrowne17/chatterbox-streaming` exposes true streaming inference with low time-to-first-audio, but it is a Python library rather than an HTTP service.

This project combines the two into a small standalone server that can fit behind existing clients such as Open WebUI, AnythingLLM, or custom integrations that already expect a `/v1/audio/speech` endpoint.

## Features

- OpenAI-style `POST /v1/audio/speech`
- True streaming inference path powered by `generate_stream()`
- Buffered fallback mode for conservative client compatibility
- Named voices backed by local reference `.wav` files
- Configurable voice registry for private voice assets outside the repo
- `GET /health`, `GET /v1/models`, and `GET /v1/voices`
- Docker and Docker Compose support

## Dependencies

`chatterbox-streaming` is installed from GitHub because the PyPI release can lag behind the streaming API this server targets. `pip install .` pulls it via the URL in `pyproject.toml`. Docker builds install the same dependency at image build time (Git is installed in the image).

### PyTorch, Blackwell (RTX 50xx), and `chatterbox-streaming`

The upstream streaming package pins **PyTorch 2.6 + CUDA 12.4** style wheels. Those builds **do not include `sm_120`**, so on **NVIDIA Blackwell (for example RTX 5090)** you can see `torch.cuda.is_available() == True` while actual model weights still fail with **“no kernel image is available for execution on the device”** unless you use a **newer PyTorch CUDA wheel set**.

**Verified reference stack** (from a working Chatterbox deployment container on the same class of GPU):

- `torch==2.7.0+cu128`
- `torchaudio==2.7.0+cu128`
- `torch.cuda.get_arch_list()` includes **`sm_120`**

This repo’s **Dockerfile** installs dependencies with `pip install .`, then **upgrades** `torch` / `torchaudio` to **2.7.0** from the **cu128** index so the image matches that proven stack. `pip` may print a **dependency conflict** warning because `chatterbox-streaming` still declares `torch==2.6.0`; that warning is expected and can be ignored as long as the image build completes.

For **local venv installs** (not Docker), upgrade after `pip install .` so the resolver does not leave you on the older pin:

```bash
pip install --upgrade torch==2.7.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128
```

On Windows PowerShell the same `pip install --upgrade ...` line applies once your venv is active.

The server **still falls back to CPU** if CUDA load fails (see `GET /health`); treat **`device_active: cpu`** on a machine with a dGPU as a signal to check PyTorch arch support, not “Chatterbox is CPU-only”.

## API Overview

### `POST /v1/audio/speech`

Accepts a JSON body compatible with common OpenAI TTS clients:

```json
{
  "input": "Hello from Chatterbox.",
  "voice": "default",
  "model": "tts-1",
  "response_format": "wav",
  "stream": false
}
```

Supported fields:

- `input` (required)
- `voice` (required)
- `model` (required, currently `tts-1`)
- `response_format` (`wav` or `pcm`)
- `stream` (`true` enables chunked streaming)
- `exaggeration`, `cfg_weight`, `temperature`, `chunk_size` as optional server extensions

Notes:

- Default mode is buffered binary audio.
- Streaming mode is enabled with `stream=true`.
- v1 intentionally keeps formats tight and production-practical: `wav` and `pcm`.

### `GET /v1/models`

Returns an OpenAI-style model list with a static `tts-1` entry.

### `GET /v1/voices`

Returns the currently registered voice names and resolved paths.

### `GET /health`

Returns readiness, selected device, CUDA visibility, and model load status.

## Quick Start

### Local Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
pip install --upgrade torch==2.7.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 4123
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install .
pip install --upgrade torch==2.7.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128
Copy-Item .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 4123
```

### Docker

```bash
cp .env.example .env
docker compose up --build
```

### Docker With GPU

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

## Voice Cloning Setup

This repo does not include any voice samples.

You have two supported ways to register voices:

1. Drop `.wav` files into the configured `VOICES_DIR`.
   - `voices/default.wav` becomes `voice=default`
   - `voices/assistant.wav` becomes `voice=assistant`
2. Point `VOICE_REGISTRY_PATH` at a JSON mapping file.

Example registry:

```json
{
  "voices": {
    "default": "./voices/default.wav",
    "assistant": "/private/path/to/assistant.wav"
  }
}
```

Registry entries override directory auto-discovery when names collide.

Voice lookups are case-insensitive.

## Open WebUI Example

This server is designed to fit an OpenAI-style TTS base URL with minimal changes:

- Base URL: `http://host.docker.internal:4123/v1`
- Engine: `openai`
- Model: `tts-1`
- Voice: a registered name such as `default`

If your client only expects a buffered audio body, leave `stream` unset or `false`.

## Configuration

Copy `.env.example` to `.env` and adjust as needed.

Common settings:

- `HOST=0.0.0.0`
- `PORT=4123`
- `DEVICE=cuda`
- `DEFAULT_VOICE=default`
- `VOICES_DIR=./voices`
- `VOICE_REGISTRY_PATH=./voice-registry.json`
- `DEFAULT_RESPONSE_FORMAT=wav`
- `DEFAULT_EXAGGERATION=0.5`
- `DEFAULT_CFG_WEIGHT=0.5`
- `DEFAULT_TEMPERATURE=0.8`
- `STREAMING_CHUNK_SIZE=25`

## Streaming Notes

The low-latency path uses `ChatterboxTTS.generate_stream()` directly instead of buffering the full synthesis result first.

For v1:

- buffered responses return complete `wav` or `pcm` bodies
- streaming responses return chunked audio bytes as they are generated
- streaming `wav` uses a chunk-friendly RIFF header with an unspecified final length

If you need client playback to start as soon as bytes arrive, prefer `stream=true`.

## Benchmark Methodology

The upstream `chatterbox-streaming` fork reports roughly sub-second first chunk latency with a `chunk_size` around `25` on high-end GPUs.

Recommended local validation:

1. Start the server on the target GPU.
2. Warm the model with one short synthesis request.
3. Measure buffered `POST /v1/audio/speech` total time.
4. Measure streaming `POST /v1/audio/speech` time-to-first-byte and total stream time.
5. Compare the results against your current buffered baseline.

For **`response_format: wav`** with **`stream: true`**, many HTTP clients (including `curl`’s `time_starttransfer`) fire as soon as the **RIFF header** is flushed, which is **not** the same as “first synthesized audio chunk.” Prefer **`response_format: pcm`** for curl-style TTFB probes, or read **`tts_stream_first_chunk`** lines from the server logs.

Actual latency depends on GPU model, CUDA stack, container runtime, driver versions, prompt length, and reference voice complexity.

## Health And Operations

- `GET /health` is intended for readiness checks and diagnostics.
- The server loads the Chatterbox model on startup by default.
- If CUDA is requested but unavailable, the service falls back to CPU and reports that state in `/health`.

## Credits

- [`resemble-ai/chatterbox`](https://github.com/resemble-ai/chatterbox)
- [`davidbrowne17/chatterbox-streaming`](https://github.com/davidbrowne17/chatterbox-streaming)

## License

MIT
