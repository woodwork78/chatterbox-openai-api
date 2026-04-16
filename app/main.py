from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers.metadata import router as metadata_router
from app.routers.speech import router as speech_router
from app.services.tts import UnsupportedAudioFormatError
from app.services.voice_registry import VoiceRegistry, VoiceRegistryError


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    base_dir = Path(__file__).resolve().parent.parent
    voice_registry = VoiceRegistry(settings, base_dir)

    from app.services.tts import TTSService

    tts_service = TTSService(settings)
    if settings.eager_model_load:
        tts_service.load()

    app.state.settings = settings
    app.state.voice_registry = voice_registry
    app.state.tts_service = tts_service
    yield
    tts_service.unload()


app = FastAPI(
    title="chatterbox-openai-api",
    version=get_settings().app_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def enforce_api_key(request: Request, call_next):
    settings = getattr(request.app.state, "settings", get_settings())
    if not settings.api_key:
        return await call_next(request)

    if request.url.path in {"/", "/health", "/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)

    expected = f"Bearer {settings.api_key}"
    if request.headers.get("authorization") != expected:
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "Unauthorized", "type": "authentication_error"}},
        )
    return await call_next(request)


app.include_router(metadata_router)
app.include_router(speech_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "chatterbox-openai-api", "status": "ok"}


@app.exception_handler(VoiceRegistryError)
async def handle_voice_registry_error(_: Request, exc: VoiceRegistryError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": {"message": str(exc), "type": "voice_registry_error"}},
    )


@app.exception_handler(UnsupportedAudioFormatError)
async def handle_audio_format_error(_: Request, exc: UnsupportedAudioFormatError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"message": str(exc), "type": "invalid_request_error"}},
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(detail), "type": "http_error"}},
    )
