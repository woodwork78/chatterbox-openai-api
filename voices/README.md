# Voices directory

Place private reference **`.wav`** files here when running locally. The Docker Compose file bind-mounts this directory to **`/app/voices`** in the container.

- **Voice id:** the filename **without** `.wav` (e.g. `lydia.wav` → use voice **`lydia`** in Open WebUI; `peter.wav` → **`peter`**).
- **Transcript:** not required for inference — Chatterbox uses the audio as the reference prompt (`audio_prompt_path` only).
- **Registry:** optional JSON mapping via **`VOICE_REGISTRY_PATH`** in `.env` (see `app/services/voice_registry.py`).

This repository intentionally does not ship voice assets.
