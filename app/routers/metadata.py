from fastapi import APIRouter, Request

from app.models import HealthResponse, ModelEntry, ModelsResponse, VoiceEntry, VoicesResponse

router = APIRouter(tags=["metadata"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    tts_service = request.app.state.tts_service
    voice_registry = request.app.state.voice_registry
    settings = request.app.state.settings
    service_health = tts_service.health()

    return HealthResponse(
        status="ok" if service_health["model_loaded"] else "degraded",
        model_loaded=bool(service_health["model_loaded"]),
        model_name=settings.model_name,
        device_requested=str(service_health["device_requested"]),
        device_active=str(service_health["device_active"]),
        cuda_available=bool(service_health["cuda_available"]),
        cuda_device_count=int(service_health["cuda_device_count"]),
        cuda_memory_allocated_mb=service_health["cuda_memory_allocated_mb"],
        cuda_memory_reserved_mb=service_health["cuda_memory_reserved_mb"],
        voices_registered=len(voice_registry.list_voices()),
        default_voice=settings.default_voice,
        load_error=service_health["load_error"],
    )


@router.get("/v1/models", response_model=ModelsResponse)
async def list_models(request: Request) -> ModelsResponse:
    settings = request.app.state.settings
    return ModelsResponse(data=[ModelEntry(id=settings.model_name)])


@router.get("/v1/voices", response_model=VoicesResponse)
async def list_voices(request: Request) -> VoicesResponse:
    voice_registry = request.app.state.voice_registry
    return VoicesResponse(
        data=[
            VoiceEntry(name=name, path=str(path))
            for name, path in voice_registry.list_voices()
        ]
    )
