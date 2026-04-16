from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "chatterbox-openai-api"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 4123
    log_level: str = "INFO"
    device: str = "cuda"
    default_voice: str | None = None
    voices_dir: Path = Path("./voices")
    voice_registry_path: Path | None = None
    model_name: str = "tts-1"
    default_response_format: Literal["wav", "pcm"] = "wav"
    default_exaggeration: float = 0.5
    default_cfg_weight: float = 0.5
    default_temperature: float = 0.8
    streaming_chunk_size: int = 25
    streaming_context_window: int = 50
    streaming_fade_duration: float = 0.02
    eager_model_load: bool = True
    max_input_length: int = 4096
    request_timeout_seconds: int = 300
    api_key: str | None = None
    trust_forwarded_headers: bool = False
    chunked_wav_header_size: int = Field(default=0xFFFFFFFF, ge=0)

    @field_validator("voice_registry_path", mode="before")
    @classmethod
    def empty_registry_path_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def resolved_voices_dir(self, base_dir: Path) -> Path:
        return self._resolve_path(self.voices_dir, base_dir)

    def resolved_voice_registry_path(self, base_dir: Path) -> Path | None:
        if self.voice_registry_path is None:
            return None
        return self._resolve_path(self.voice_registry_path, base_dir)

    @staticmethod
    def _resolve_path(path: Path, base_dir: Path) -> Path:
        if path.is_absolute():
            return path
        return (base_dir / path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
