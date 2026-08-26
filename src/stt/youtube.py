from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from stt.segment import Segment


DEFAULT_MOST_RATED_COMMENTS = 10


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


@dataclass(slots=True)
class Comment:
    """Comentario de YouTube con su conteo de likes."""

    id: str

    author: str

    text: str

    like_count: int


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


class DownloadCancelled(Exception):
    """El usuario canceló la descarga de audio de YouTube."""


def download_audio(
    url: str,
    out_dir: Path,
    *,
    on_progress=None,
    should_cancel=None,
) -> Path:
    """Descarga el mejor audio del video y lo extrae a WAV con ffmpeg.

    Se usa como respaldo cuando el video no tiene captions y se
    transcribirá con faster-whisper (paso 2).

    ``on_progress`` recibe el dict del progress hook de yt-dlp.
    ``should_cancel`` se consulta tras metadata y en cada hook; si
    devuelve True se lanza ``DownloadCancelled``.
    """

    from yt_dlp import YoutubeDL

    out_dir.mkdir(parents=True, exist_ok=True)

    def _check_cancel() -> None:

        if should_cancel is not None and should_cancel():

            raise DownloadCancelled("Descarga cancelada por el usuario.")

    def _hook(d: dict) -> None:

        _check_cancel()

        if on_progress is not None:

            on_progress(d)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # Preferir contenedores de audio estables; el CDN a veces
        # corta conexiones y conviene reintentar con más paciencia.
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "socket_timeout": 60,
        "retries": 15,
        "fragment_retries": 15,
        "file_access_retries": 5,
        "extractor_retries": 5,
        # node/bun suelen estar en el PATH; deno es el default de yt-dlp.
        "js_runtimes": {"node": {}, "bun": {}, "deno": {}},
        "progress_hooks": [_hook],
        "retry_sleep_functions": {
            "http": lambda n: min(2 ** n, 30),
            "fragment": lambda n: min(2 ** n, 30),
            "extractor": lambda n: min(2 ** n, 20),
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
    }

    with YoutubeDL(opts) as ydl:

        # Metadata primero: permite abortar con "x" antes del CDN.
        info = ydl.extract_info(url, download=False)

        _check_cancel()

        ydl.process_ie_result(info, download=True)

    return out_dir / f"{info['id']}.wav"


def fetch_top_comments(
    video_id: str,
    n: int = DEFAULT_MOST_RATED_COMMENTS,
) -> list[Comment]:
    """Obtiene los n comentarios raíz con más likes del video.

    Usa la ordenación «top» de YouTube vía yt-dlp y reordena por
    ``like_count``. Devuelve lista vacía si no hay comentarios o fallan.
    """

    if n <= 0:

        return []

    from yt_dlp import YoutubeDL

    # Pedimos un lote mayor que n: el «top» de YouTube no es solo likes.
    fetch_limit = max(n * 5, 50)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "getcomments": True,
        "extractor_args": {
            "youtube": {
                # max_comments, max_parents, max_replies
                "max_comments": [str(fetch_limit), str(fetch_limit), "0"],
                "comment_sort": ["top"],
            }
        },
    }

    try:

        with YoutubeDL(opts) as ydl:

            info = ydl.extract_info(watch_url(video_id), download=False)

    except Exception:  # noqa: BLE001

        return []

    comments: list[Comment] = []

    for raw in info.get("comments") or []:

        if not raw:

            continue

        parent = raw.get("parent")

        if parent not in (None, "root"):

            continue

        text = (raw.get("text") or "").strip()

        if not text:

            continue

        try:

            likes = int(raw.get("like_count") or 0)

        except (TypeError, ValueError):

            likes = 0

        comments.append(
            Comment(
                id=str(raw.get("id") or ""),
                author=(raw.get("author") or "Anónimo").strip() or "Anónimo",
                text=text,
                like_count=max(likes, 0),
            )
        )

    comments.sort(key=lambda c: c.like_count, reverse=True)

    return comments[:n]


def write_comments(
    comments: list[Comment],
    out_dir: Path,
    stem: str,
    title: str,
) -> Path:
    """Escribe los comentarios más votados en Markdown junto a la transcripción."""

    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / f"{stem}-comments.md"

    lines = [f"# Comentarios más votados — {title}", ""]

    if not comments:

        lines.append("_No se encontraron comentarios._")

        lines.append("")

    else:

        for i, comment in enumerate(comments, start=1):

            lines.append(
                f"## {i}. {comment.author} ({comment.like_count} likes)"
            )

            lines.append("")

            lines.append(comment.text)

            lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf8")

    return path
