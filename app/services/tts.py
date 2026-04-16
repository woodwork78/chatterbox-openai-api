from __future__ import annotations

import gc
import io
import logging
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable
from uuid import uuid4

from app.config import Settings

LOGGER = logging.getLogger(__name__)


class TTSServiceError(Exception):
    """Base exception for TTS service failures."""


class ModelNotLoadedError(TTSServiceError):
    """Raised when the TTS model is unavailable."""


class UnsupportedAudioFormatError(TTSServiceError):
    """Raised when the requested audio format is unsupported."""


@dataclass
class BufferedAudioResult:
    request_id: str
    content: bytes
    media_type: str
    response_format: str
    total_time_seconds: float


@dataclass
class StreamingAudioResult:
    request_id: str
    media_type: str
    response_format: str
    iterator: Iterable[bytes]


class TTSService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._generation_lock = threading.Lock()
        self._model = None
        self._torch = None
        self._active_device = "uninitialized"
        self._load_error: str | None = None
        self._sample_rate: int | None = None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    @property
    def active_device(self) -> str:
        return self._active_device

    @property
    def sample_rate(self) -> int:
        if self._sample_rate is None:
            raise ModelNotLoadedError("Model sample rate is unavailable because the model is not loaded")
        return self._sample_rate

    def load(self) -> None:
        try:
            import torch
            from chatterbox.tts import ChatterboxTTS

            self._torch = torch
            device = self._resolve_device(torch)
            started = time.perf_counter()
            model = ChatterboxTTS.from_pretrained(device)
            self._model = model
            self._sample_rate = int(model.sr)
            self._active_device = str(device)
            self._load_error = None
            LOGGER.info(
                "Loaded Chatterbox model on %s in %.2fs",
                self._active_device,
                time.perf_counter() - started,
            )
        except Exception as exc:  # pragma: no cover - runtime integration path
            self._model = None
            self._sample_rate = None
            self._active_device = "unavailable"
            self._load_error = str(exc)
            LOGGER.exception("Failed to load Chatterbox model")

    def unload(self) -> None:
        self._model = None
        self._sample_rate = None
        gc.collect()
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    def health(self) -> dict[str, object]:
        cuda_available = False
        cuda_device_count = 0
        allocated_mb = None
        reserved_mb = None

        torch_module = self._torch
        if torch_module is None:
            try:
                import torch as torch_probe

                torch_module = torch_probe
            except ImportError:
                torch_module = None

        if torch_module is not None:
            cuda_available = bool(torch_module.cuda.is_available())
            cuda_device_count = int(torch_module.cuda.device_count()) if cuda_available else 0
            if cuda_available and self._torch is not None:
                allocated_mb = round(float(self._torch.cuda.memory_allocated()) / 1024 / 1024, 2)
                reserved_mb = round(float(self._torch.cuda.memory_reserved()) / 1024 / 1024, 2)

        return {
            "model_loaded": self.model_loaded,
            "device_active": self._active_device,
            "device_requested": self._settings.device,
            "cuda_available": cuda_available,
            "cuda_device_count": cuda_device_count,
            "cuda_memory_allocated_mb": allocated_mb,
            "cuda_memory_reserved_mb": reserved_mb,
            "load_error": self._load_error,
        }

    def generate_buffered(
        self,
        *,
        text: str,
        voice_name: str,
        voice_path: Path,
        response_format: str,
        exaggeration: float,
        cfg_weight: float,
        temperature: float,
    ) -> BufferedAudioResult:
        request_id = uuid4().hex[:12]
        model = self._require_model()
        media_type = self._media_type_for_format(response_format)
        started = time.perf_counter()

        with self._generation_lock:
            audio = model.generate(
                text,
                audio_prompt_path=str(voice_path),
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )

        pcm_bytes = self._tensor_to_pcm_bytes(audio)
        content = self._encode_output(
            pcm_bytes=pcm_bytes,
            response_format=response_format,
            sample_rate=self.sample_rate,
            stream=False,
        )
        total_time = time.perf_counter() - started
        LOGGER.info(
            "tts_buffered request_id=%s voice=%s format=%s bytes=%s total_s=%.3f",
            request_id,
            voice_name,
            response_format,
            len(content),
            total_time,
        )
        return BufferedAudioResult(
            request_id=request_id,
            content=content,
            media_type=media_type,
            response_format=response_format,
            total_time_seconds=total_time,
        )

    def generate_streaming(
        self,
        *,
        text: str,
        voice_name: str,
        voice_path: Path,
        response_format: str,
        exaggeration: float,
        cfg_weight: float,
        temperature: float,
        chunk_size: int,
    ) -> StreamingAudioResult:
        request_id = uuid4().hex[:12]
        model = self._require_model()
        media_type = self._media_type_for_format(response_format)
        sample_rate = self.sample_rate

        def iterator() -> Generator[bytes, None, None]:
            started = time.perf_counter()
            first_chunk_time: float | None = None
            chunk_count = 0

            if response_format == "wav":
                yield self._wav_header(sample_rate, self._settings.chunked_wav_header_size)

            with self._generation_lock:
                for chunk, metrics in model.generate_stream(
                    text,
                    audio_prompt_path=str(voice_path),
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    temperature=temperature,
                    chunk_size=chunk_size,
                    context_window=self._settings.streaming_context_window,
                    fade_duration=self._settings.streaming_fade_duration,
                    print_metrics=False,
                ):
                    chunk_count += 1
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter() - started
                        LOGGER.info(
                            "tts_stream_first_chunk request_id=%s voice=%s format=%s chunk_size=%s first_chunk_s=%.3f upstream_first_chunk_s=%s",
                            request_id,
                            voice_name,
                            response_format,
                            chunk_size,
                            first_chunk_time,
                            getattr(metrics, "latency_to_first_chunk", None),
                        )
                    yield self._tensor_to_pcm_bytes(chunk)

            total_time = time.perf_counter() - started
            LOGGER.info(
                "tts_stream_complete request_id=%s voice=%s format=%s chunk_size=%s chunks=%s total_s=%.3f",
                request_id,
                voice_name,
                response_format,
                chunk_size,
                chunk_count,
                total_time,
            )

        return StreamingAudioResult(
            request_id=request_id,
            media_type=media_type,
            response_format=response_format,
            iterator=iterator(),
        )

    def resolve_response_format(self, requested_format: str | None) -> str:
        return requested_format or self._settings.default_response_format

    def _require_model(self):
        if self._model is None:
            raise ModelNotLoadedError(self._load_error or "Chatterbox model is not loaded")
        return self._model

    def _resolve_device(self, torch_module) -> str:
        requested = self._settings.device.lower()
        if requested == "cuda" and not torch_module.cuda.is_available():
            LOGGER.warning("CUDA requested but unavailable; falling back to CPU")
            return "cpu"
        return requested

    def _media_type_for_format(self, response_format: str) -> str:
        if response_format == "wav":
            return "audio/wav"
        if response_format == "pcm":
            return "audio/pcm"
        raise UnsupportedAudioFormatError(
            f"Unsupported response_format '{response_format}'. Supported formats: wav, pcm."
        )

    def _encode_output(
        self,
        *,
        pcm_bytes: bytes,
        response_format: str,
        sample_rate: int,
        stream: bool,
    ) -> bytes:
        if response_format == "pcm":
            return pcm_bytes
        if response_format == "wav":
            if stream:
                return self._wav_header(sample_rate, self._settings.chunked_wav_header_size) + pcm_bytes
            return self._encode_wav_bytes(pcm_bytes, sample_rate)
        raise UnsupportedAudioFormatError(
            f"Unsupported response_format '{response_format}'. Supported formats: wav, pcm."
        )

    def _encode_wav_bytes(self, pcm_bytes: bytes, sample_rate: int) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()

    def _wav_header(self, sample_rate: int, data_size: int) -> bytes:
        byte_rate = sample_rate * 2
        block_align = 2
        riff_size = 36 + data_size
        return (
            b"RIFF"
            + int(riff_size & 0xFFFFFFFF).to_bytes(4, "little", signed=False)
            + b"WAVEfmt "
            + (16).to_bytes(4, "little", signed=False)
            + (1).to_bytes(2, "little", signed=False)
            + (1).to_bytes(2, "little", signed=False)
            + int(sample_rate).to_bytes(4, "little", signed=False)
            + int(byte_rate).to_bytes(4, "little", signed=False)
            + int(block_align).to_bytes(2, "little", signed=False)
            + (16).to_bytes(2, "little", signed=False)
            + b"data"
            + int(data_size & 0xFFFFFFFF).to_bytes(4, "little", signed=False)
        )

    def _tensor_to_pcm_bytes(self, tensor) -> bytes:
        if self._torch is None:
            raise ModelNotLoadedError("Torch is not available")

        audio_tensor = tensor.detach().cpu().flatten().clamp(-1.0, 1.0)
        pcm_tensor = (audio_tensor * 32767.0).to(self._torch.int16)
        return pcm_tensor.numpy().tobytes()
