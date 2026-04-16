# Chatterbox OpenAI API

OpenAI-compatible API for Chatterbox streaming TTS, with voice cloning, named voices, and Docker-first deployment.

This project wraps low-latency local Chatterbox streaming inference in a simple HTTP service that works with tools expecting the OpenAI speech API shape, including `POST /v1/audio/speech`. It is designed for local/private voice cloning workflows, reproducible Docker deployment, and drop-in integration with apps like Open WebUI.

## Goals

- Provide an OpenAI-compatible TTS endpoint for local Chatterbox inference
- Support low-latency streaming-backed generation
- Support voice cloning from reference audio files
- Support named voices mapped to local reference WAV files
- Run cleanly in Docker with GPU acceleration
- Stay simple enough to use as both a personal service and a reusable public project

## Planned Features

- `POST /v1/audio/speech`
- `GET /health`
- Named voice registry
- Voice cloning from local reference audio
- OpenAI-compatible request format
- Docker-first deployment
- Optional streaming/SSE endpoints
- Optional `/v1/models` and `/v1/voices`

## Example Use Cases

- Open WebUI local TTS integration
- Private assistant voice cloning
- Low-latency local speech generation
- Self-hosted OpenAI-compatible speech API
- Named household/family voice profiles backed by local reference audio

## Status

Early build. The goal is to provide a stable OpenAI-compatible wrapper around Chatterbox streaming inference with minimal integration friction.

## Why This Exists

Chatterbox streaming inference can achieve much better latency than some existing local wrappers, but the model-level streaming implementation does not itself provide the HTTP API surface that many tools expect. This project fills that gap by exposing a practical service layer around Chatterbox that can fit existing app architectures with minimal change.

## Design Principles

- Local-first
- Private voice assets remain user-controlled
- OpenAI-compatible where practical
- Minimal dependencies beyond what is needed
- Clear configuration over hidden behavior
- Good defaults, easy overrides

## Non-Goals

- Bundling private voice assets
- Tying the project to one specific frontend
- Requiring Open WebUI-specific code paths
- Replacing the Chatterbox model itself

## License

MIT
