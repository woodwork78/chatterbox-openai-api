from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.models import ErrorBody, ErrorResponse, SpeechRequest
from app.services.tts import ModelNotLoadedError, TTSService, TTSServiceError, UnsupportedAudioFormatError
from app.services.voice_registry import VoiceNotFoundError, VoiceRegistry

router = APIRouter(tags=["speech"])


def _get_tts_service(request: Request) -> TTSService:
    return request.app.state.tts_service


def _get_voice_registry(request: Request) -> VoiceRegistry:
    return request.app.state.voice_registry


@router.post(
    "/v1/audio/speech",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def create_speech(request: Request, payload: SpeechRequest) -> Response:
    settings = request.app.state.settings
    if len(payload.input) > settings.max_input_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorBody(
                    message=f"input exceeds MAX_INPUT_LENGTH={settings.max_input_length}.",
                    type="invalid_request_error",
                )
            ).model_dump(),
        )

    if payload.model != settings.model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorBody(
                    message=f"Unsupported model '{payload.model}'. Supported model: {settings.model_name}.",
                    type="invalid_request_error",
                )
            ).model_dump(),
        )

    if payload.speed != 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorBody(
                    message="speed is not supported by this server yet; use the default value of 1.0.",
                    type="invalid_request_error",
                )
            ).model_dump(),
        )

    tts_service = _get_tts_service(request)
    voice_registry = _get_voice_registry(request)

    try:
        resolved_voice_name, voice_path = voice_registry.resolve(payload.voice)
        response_format = tts_service.resolve_response_format(payload.response_format)
        exaggeration = payload.exaggeration if payload.exaggeration is not None else settings.default_exaggeration
        cfg_weight = payload.cfg_weight if payload.cfg_weight is not None else settings.default_cfg_weight
        temperature = payload.temperature if payload.temperature is not None else settings.default_temperature
        chunk_size = payload.chunk_size if payload.chunk_size is not None else settings.streaming_chunk_size

        if payload.stream:
            result = tts_service.generate_streaming(
                text=payload.input,
                voice_name=resolved_voice_name,
                voice_path=voice_path,
                response_format=response_format,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
                chunk_size=chunk_size,
            )
            return StreamingResponse(
                result.iterator,
                media_type=result.media_type,
                headers={
                    "X-Request-Id": result.request_id,
                    "X-Response-Format": result.response_format,
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-store",
                },
            )

        result = await run_in_threadpool(
            tts_service.generate_buffered,
            text=payload.input,
            voice_name=resolved_voice_name,
            voice_path=voice_path,
            response_format=response_format,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
        )
        return Response(
            content=result.content,
            media_type=result.media_type,
            headers={
                "X-Request-Id": result.request_id,
                "X-Response-Format": result.response_format,
                "X-Total-Time-Seconds": f"{result.total_time_seconds:.3f}",
                "Cache-Control": "no-store",
            },
        )
    except VoiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error=ErrorBody(message=str(exc), type="voice_not_found")
            ).model_dump(),
        ) from exc
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorBody(message=str(exc), type="model_unavailable")
            ).model_dump(),
        ) from exc
    except UnsupportedAudioFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorBody(message=str(exc), type="invalid_request_error")
            ).model_dump(),
        ) from exc
    except TTSServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorBody(message=str(exc), type="tts_error")
            ).model_dump(),
        ) from exc
