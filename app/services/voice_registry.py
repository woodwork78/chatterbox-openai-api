from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import Settings

LOGGER = logging.getLogger(__name__)


class VoiceRegistryError(Exception):
    """Base exception for voice registry failures."""


class VoiceNotFoundError(VoiceRegistryError):
    """Raised when a requested voice is not registered."""


class VoiceRegistry:
    def __init__(self, settings: Settings, base_dir: Path) -> None:
        self._settings = settings
        self._voices_dir = settings.resolved_voices_dir(base_dir)
        self._registry_path = settings.resolved_voice_registry_path(base_dir)
        self._voices: dict[str, tuple[str, Path]] = {}
        self.reload()

    @property
    def voices_dir(self) -> Path:
        return self._voices_dir

    def reload(self) -> None:
        self._voices_dir.mkdir(parents=True, exist_ok=True)

        discovered: dict[str, tuple[str, Path]] = {}
        for path in sorted(self._voices_dir.glob("*.wav")):
            discovered[path.stem.casefold()] = (path.stem, path.resolve())

        configured = self._load_registry_file()
        discovered.update(configured)
        self._voices = discovered

    def _load_registry_file(self) -> dict[str, tuple[str, Path]]:
        if self._registry_path is None:
            return {}
        if not self._registry_path.exists() or self._registry_path.is_dir():
            return {}

        with self._registry_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        voices = payload.get("voices", payload)
        if not isinstance(voices, dict):
            raise VoiceRegistryError("voice registry file must contain an object mapping names to paths")

        registry_base = self._registry_path.parent
        loaded: dict[str, tuple[str, Path]] = {}
        for raw_name, raw_path in voices.items():
            if not isinstance(raw_name, str) or not isinstance(raw_path, str):
                raise VoiceRegistryError("voice registry keys and values must be strings")

            name = raw_name.strip()
            if not name:
                raise VoiceRegistryError("voice registry contains an empty name")

            path = Path(raw_path.strip())
            if not path.is_absolute():
                path = (registry_base / path).resolve()
            else:
                path = path.resolve()

            if not path.exists():
                LOGGER.warning("Skipping voice '%s'; file does not exist: %s", name, path)
                continue

            loaded[name.casefold()] = (name, path)

        return loaded

    def list_voices(self) -> list[tuple[str, Path]]:
        return sorted(self._voices.values(), key=lambda item: item[0].casefold())

    def resolve(self, requested_voice: str | None) -> tuple[str, Path]:
        name = (requested_voice or self._settings.default_voice or "").strip()
        if not name:
            raise VoiceNotFoundError("No voice was provided and DEFAULT_VOICE is not configured")

        match = self._voices.get(name.casefold())
        if match is None:
            raise VoiceNotFoundError(
                f"Voice '{name}' is not registered. Add a .wav file to {self._voices_dir} or configure VOICE_REGISTRY_PATH."
            )
        return match
