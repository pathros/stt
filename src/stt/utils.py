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
    """Expande ~ y variables de entorno, y resuelve a ruta absoluta.

    También tolera rutas pegadas con escapes del shell (p. ej. ``Audio\\ Hijack``)
    o entre comillas literales.
    """

    import os
    import re

    text = str(path).strip()

    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":

        text = text[1:-1]

    text = os.path.expandvars(text)

    expanded = Path(text).expanduser()

    if expanded.exists():

        return expanded.resolve()

    # Ruta escapada del shell pegada literalmente: Audio\ Hijack → Audio Hijack
    if "\\" in text:

        unescaped = Path(re.sub(r"\\(.)", r"\1", text)).expanduser()

        if unescaped.exists():

            return unescaped.resolve()

    return expanded.resolve()


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
