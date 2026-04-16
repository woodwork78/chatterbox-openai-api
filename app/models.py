from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input: str = Field(..., min_length=1, max_length=4096)
    voice: str = Field(..., min_length=1)
    model: str = Field(default="tts-1", min_length=1)
    response_format: Literal["wav", "pcm"] | None = None
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    stream: bool = False
    exaggeration: float | None = Field(default=None, ge=0.0)
    cfg_weight: float | None = Field(default=None, ge=0.0)
    temperature: float | None = Field(default=None, ge=0.0)
    chunk_size: int | None = Field(default=None, ge=1)

    @field_validator("input")
    @classmethod
    def strip_input(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("input must not be empty")
        return stripped

    @field_validator("voice", "model")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped


class VoiceEntry(BaseModel):
    name: str
    path: str


class VoicesResponse(BaseModel):
    object: str = "list"
    data: list[VoiceEntry]


class ModelEntry(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "local"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelEntry]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_loaded: bool
    model_name: str
    device_requested: str
    device_active: str
    cuda_available: bool
    cuda_device_count: int
    cuda_memory_allocated_mb: float | None = None
    cuda_memory_reserved_mb: float | None = None
    voices_registered: int
    default_voice: str | None
    load_error: str | None = None


class ErrorBody(BaseModel):
    message: str
    type: str


class ErrorResponse(BaseModel):
    error: ErrorBody
