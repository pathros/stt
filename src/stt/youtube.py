from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from stt.segment import Segment


@dataclass(slots=True)
class VideoRef:
    """Referencia mínima a un video de YouTube."""

    id: str

    title: str

    url: str


@dataclass(slots=True)
class ParsedUrl:
    """Resultado de analizar una URL de YouTube."""

    video_id: str | None

    playlist_id: str | None


def parse_youtube_url(url: str) -> ParsedUrl:
    """Extrae video_id y/o playlist_id de una URL de YouTube."""

    u = urlparse(url)

    qs = parse_qs(u.query)

    video_id = qs.get("v", [None])[0]

    playlist_id = qs.get("list", [None])[0]

    host = u.netloc.lower()

    if host.endswith("youtu.be"):

        video_id = u.path.lstrip("/") or video_id

    # En URLs de tipo /playlist solo importa la lista.
    if u.path.startswith("/playlist"):

        video_id = None

    return ParsedUrl(video_id=video_id, playlist_id=playlist_id)


def watch_url(video_id: str) -> str:

    return f"https://www.youtube.com/watch?v={video_id}"


def get_video_info(url_or_id: str) -> VideoRef:
    """Obtiene id y título de un solo video (metadata, sin descarga)."""

    from yt_dlp import YoutubeDL

    url = url_or_id

    if "://" not in url_or_id:

        url = watch_url(url_or_id)

    opts = {"quiet": True, "no_warnings": True, "skip_download": True}

    with YoutubeDL(opts) as ydl:

        info = ydl.extract_info(url, download=False)

    return VideoRef(
        id=info["id"],
        title=info.get("title", info["id"]),
        url=watch_url(info["id"]),
    )


def list_playlist(playlist_id: str) -> list[VideoRef]:
    """Enumera los videos de una playlist (rápido, sin descargar)."""

    from yt_dlp import YoutubeDL

    url = f"https://www.youtube.com/playlist?list={playlist_id}"

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
    }

    with YoutubeDL(opts) as ydl:

        info = ydl.extract_info(url, download=False)

    videos: list[VideoRef] = []

    for entry in info.get("entries") or []:

        if not entry:

            continue

        vid = entry.get("id")

        if not vid:

            continue

        videos.append(
            VideoRef(
                id=vid,
                title=entry.get("title") or vid,
                url=watch_url(vid),
            )
        )

    return videos


def fetch_captions(
    video_id: str,
    languages: list[str],
) -> tuple[list[Segment], str, bool] | None:
    """Extrae los captions ya existentes del video (el botón "Mostrar transcripción").

    Devuelve (segmentos, idioma, es_autogenerado) o None si no hay captions.
    """

    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        YouTubeTranscriptApiException,
    )
    from youtube_transcript_api import NoTranscriptFound

    api = YouTubeTranscriptApi()

    try:

        listing = api.list(video_id)

    except YouTubeTranscriptApiException:

        return None

    try:

        transcript = listing.find_transcript(languages)

    except NoTranscriptFound:

        transcript = next(iter(listing), None)

        if transcript is None:

            return None

    try:

        raw = transcript.fetch().to_raw_data()

    except YouTubeTranscriptApiException:

        return None

    segments = [
        Segment(
            start=float(d["start"]),
            end=float(d["start"]) + float(d.get("duration", 0.0)),
            text=d["text"],
        )
        for d in raw
    ]

    return segments, transcript.language_code, transcript.is_generated


def download_audio(url: str, out_dir: Path) -> Path:
    """Descarga el mejor audio del video y lo extrae a WAV con ffmpeg.

    Se usa como respaldo cuando el video no tiene captions y se
    transcribirá con faster-whisper (paso 2).
    """

    from yt_dlp import YoutubeDL

    out_dir.mkdir(parents=True, exist_ok=True)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
    }

    with YoutubeDL(opts) as ydl:

        info = ydl.extract_info(url, download=True)

    return out_dir / f"{info['id']}.wav"
