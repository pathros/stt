from __future__ import annotations

from pathlib import Path


AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".opus",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".mp4",
    ".mkv",
    ".webm",
}


def human_duration(seconds: float) -> str:
    """Formatea una duración en segundos como HH:MM:SS o MM:SS."""

    seconds = int(round(seconds))

    hours, remainder = divmod(seconds, 3600)

    minutes, secs = divmod(remainder, 60)

    if hours:

        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def expand_path(path: str | Path) -> Path:
    """Expande ~ y variables de entorno, y resuelve a ruta absoluta."""

    import os

    text = os.path.expandvars(str(path))

    return Path(text).expanduser().resolve()


def detect_audio(path: str | Path) -> bool:
    """Indica si la ruta apunta a un archivo de audio/vídeo soportado."""

    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


def safe_filename(name: str, max_len: int = 120) -> str:
    """Convierte un título en un nombre de archivo seguro."""

    import re

    name = name.strip()

    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)

    name = re.sub(r"\s+", " ", name)

    name = name.strip(". ")

    return (name[:max_len].strip() or "transcripcion")
