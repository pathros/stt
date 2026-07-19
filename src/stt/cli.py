from __future__ import annotations

from pathlib import Path

from rich.prompt import Prompt

from stt.config import Config, save_config
from stt.utils import detect_audio, expand_path, safe_filename, human_duration
from stt.segment import write_many, SUPPORTED_FORMATS
from stt.youtube import (
    parse_youtube_url,
    get_video_info,
    list_playlist,
    fetch_captions,
    download_audio,
    VideoRef,
)
from stt.formatter import (
    banner,
    main_menu,
    section,
    show_config,
    console,
    info,
    warn,
    error,
)


def run_menu(cfg: Config) -> None:
    """Modo guiado: muestra el menú y despacha la opción elegida."""

    banner()

    while True:

        print()

        main_menu()

        print()

        choice = Prompt.ask(
            ">",
            choices=["1", "2", "3", "4"],
            show_choices=False,
        )

        if choice == "1":

            handle_local(cfg)

        elif choice == "2":

            handle_youtube(cfg)

        elif choice == "3":

            handle_config(cfg)

        elif choice == "4":

            console.print("[dim]Hasta luego.[/dim]")

            return


def handle_local(
    cfg: Config,
    path: str | None = None,
    formats: list[str] | None = None,
    timestamps: bool | None = None,
    minutes: float | None = None,
) -> None:
    """Transcribe un archivo local con faster-whisper."""

    section("Archivo local")

    if path is None:

        path = Prompt.ask("Ruta del archivo").strip()

    audio = expand_path(path)

    if not audio.exists():

        error(f"El archivo no existe: {audio}")

        return

    if not detect_audio(audio):

        warn("La extensión no parece de audio/vídeo soportado.")

    if formats is None:

        chosen = Prompt.ask(
            "Formato(s) de salida",
            default=", ".join(cfg.formats),
        )

        formats = [f.strip() for f in chosen.split(",") if f.strip()]

    if timestamps is None:

        timestamps = Prompt.ask(
            "¿Incluir marcas de tiempo?",
            choices=["s", "n"],
            default="n",
        ) == "s"

    invalid = [f for f in formats if f.lstrip(".").lower() not in SUPPORTED_FORMATS]

    if invalid:

        error(f"Formato(s) no soportado(s): {', '.join(invalid)}")

        return

    info(f"Archivo: {audio}")

    info(f"Modelo: {cfg.model} ({cfg.compute_type}, CPU) · idioma: {cfg.language}")

    if minutes:

        warn(f"Vista previa: solo los primeros {minutes:g} min.")

    _run_whisper(
        cfg,
        audio,
        formats,
        timestamps,
        stem=safe_filename(audio.stem),
        title=audio.stem,
        minutes=minutes,
    )


def _run_whisper(
    cfg: Config,
    audio: Path,
    formats: list[str],
    timestamps: bool,
    stem: str,
    title: str,
    minutes: float | None = None,
) -> None:
    """Transcribe un archivo de audio con faster-whisper y escribe la salida."""

    from stt.transcriber import transcribe
    from stt.progress import transcription_progress

    print()

    try:

        with console.status(
            "[cyan]Cargando modelo y analizando audio… "
            "(la 1ª vez descarga el modelo)[/cyan]",
            spinner="dots",
        ):

            tinfo, seg_iter = transcribe(audio, cfg, minutes=minutes)

    except Exception as exc:  # noqa: BLE001

        error(f"No se pudo iniciar la transcripción: {exc}")

        return

    detected = getattr(tinfo, "language", None)

    total = getattr(tinfo, "duration", 0.0) or 0.0

    if minutes:

        total = min(total, float(minutes) * 60)

    console.print(
        f"[dim]Duración: {human_duration(total)} · "
        f"idioma detectado: {detected}[/dim]"
    )

    segments = []

    with transcription_progress(total) as update:

        for seg in seg_iter:

            segments.append(seg)

            update(seg.end)

    if not segments:

        warn("No se obtuvo texto (¿audio en silencio o VAD muy agresivo?).")

        return

    paths = write_many(
        segments,
        cfg.output,
        stem,
        formats,
        timestamps=timestamps,
        title=title,
    )

    print()

    for p in paths:

        info(f"Guardado → {p}")


def _caption_languages(cfg: Config) -> list[str]:
    """Orden de preferencia de idioma para los captions."""

    langs: list[str] = []

    if cfg.language and cfg.language != "auto":

        langs.append(cfg.language)

    for fallback in ("es", "es-MX", "es-419", "en"):

        if fallback not in langs:

            langs.append(fallback)

    return langs


def _resolve_videos(url: str) -> list[VideoRef]:
    """Determina qué video(s) transcribir según la URL."""

    parsed = parse_youtube_url(url)

    if parsed.playlist_id and parsed.video_id:

        choice = Prompt.ask(
            "El enlace tiene un video y una playlist. ¿Qué transcribo?",
            choices=["v", "p"],
            default="v",
        )

        if choice == "p":

            return list_playlist(parsed.playlist_id)

        return [get_video_info(parsed.video_id)]

    if parsed.playlist_id:

        return list_playlist(parsed.playlist_id)

    if parsed.video_id:

        return [get_video_info(parsed.video_id)]

    return [get_video_info(url)]


def _whisper_youtube(
    cfg: Config,
    video: VideoRef,
    formats: list[str],
    timestamps: bool,
) -> None:
    """Descarga el audio del video y lo transcribe con faster-whisper."""

    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="stt_yt_"))

    try:

        with console.status(
            "[cyan]Descargando audio del video…[/cyan]",
            spinner="dots",
        ):

            audio = download_audio(video.url, tmp)

        _run_whisper(
            cfg,
            audio,
            formats,
            timestamps,
            stem=safe_filename(video.title),
            title=video.title,
        )

    finally:

        shutil.rmtree(tmp, ignore_errors=True)


def _process_video(
    cfg: Config,
    video: VideoRef,
    languages: list[str],
    formats: list[str],
    timestamps: bool,
    use_whisper: bool,
) -> None:
    """Transcribe un video: captions primero, Whisper como respaldo (o forzado)."""

    console.print(f"[cyan]▶[/cyan] {video.title}")

    if not use_whisper:

        result = fetch_captions(video.id, languages)

        if result is not None:

            segments, lang, generated = result

            origen = "auto-generados" if generated else "manuales"

            paths = write_many(
                segments,
                cfg.output,
                safe_filename(video.title),
                formats,
                timestamps=timestamps,
                title=video.title,
            )

            for p in paths:

                info(f"Captions {origen} ({lang}) → {p}")

            return

        warn("Sin captions disponibles; usando Whisper como respaldo…")

    _whisper_youtube(cfg, video, formats, timestamps)


def handle_youtube(
    cfg: Config,
    url: str | None = None,
    formats: list[str] | None = None,
    timestamps: bool | None = None,
    use_whisper: bool = False,
) -> None:
    """Ingesta desde una URL de YouTube (video o playlist)."""

    section("YouTube")

    if url is None:

        url = Prompt.ask("YouTube URL").strip()

    if not url:

        error("No se proporcionó una URL.")

        return

    try:

        videos = _resolve_videos(url)

    except Exception as exc:  # noqa: BLE001

        error(f"No se pudo leer la URL: {exc}")

        return

    if not videos:

        error("No se encontraron videos en el enlace.")

        return

    if formats is None:

        chosen = Prompt.ask(
            "Formato(s) de salida",
            default=", ".join(cfg.formats),
        )

        formats = [f.strip() for f in chosen.split(",") if f.strip()]

    if timestamps is None:

        timestamps = Prompt.ask(
            "¿Incluir marcas de tiempo?",
            choices=["s", "n"],
            default="n",
        ) == "s"

    invalid = [f for f in formats if f.lstrip(".").lower() not in SUPPORTED_FORMATS]

    if invalid:

        error(f"Formato(s) no soportado(s): {', '.join(invalid)}")

        return

    info(f"{len(videos)} video(s) a procesar.")

    if use_whisper:

        warn("Modo Whisper forzado: se ignoran los captions de YouTube.")

    languages = _caption_languages(cfg)

    print()

    for video in videos:

        try:

            _process_video(cfg, video, languages, formats, timestamps, use_whisper)

        except Exception as exc:  # noqa: BLE001

            error(f"Error con «{video.title}»: {exc}")


def handle_config(cfg: Config) -> None:
    """Muestra y permite editar la configuración."""

    section("Configuración")

    show_config(cfg)

    print()

    if Prompt.ask(
        "¿Editar configuración?",
        choices=["s", "n"],
        default="n",
    ) == "n":

        return

    cfg.model = Prompt.ask("Modelo", default=cfg.model)

    cfg.language = Prompt.ask("Idioma", default=cfg.language)

    cfg.output = expand_path(
        Prompt.ask("Carpeta de salida", default=str(cfg.output))
    )

    formats = Prompt.ask(
        "Formatos (separados por coma)",
        default=", ".join(cfg.formats),
    )

    cfg.formats = [f.strip() for f in formats.split(",") if f.strip()]

    save_config(cfg)

    info("Configuración guardada.")


