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
    fetch_top_comments,
    write_comments,
    download_audio,
    DownloadCancelled,
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


def _ask_formats(cfg: Config) -> list[str]:
    """Pregunta formato(s) de salida mostrando las opciones posibles."""

    available = ", ".join(SUPPORTED_FORMATS)

    chosen = Prompt.ask(
        f"Formato(s) de salida ({available})",
        default=", ".join(cfg.formats),
    )

    return [f.strip() for f in chosen.split(",") if f.strip()]


def run_menu(cfg: Config) -> None:
    """Modo guiado: muestra el menú y despacha la opción elegida."""

    banner()

    while True:

        print()

        main_menu()

        print()

        choice = Prompt.ask(
            ">",
            choices=["1", "2", "3", "4", "5"],
            show_choices=False,
        )

        if choice == "1":

            handle_local(cfg)

        elif choice == "2":

            handle_youtube(cfg)

        elif choice == "3":

            handle_podcast(cfg)

        elif choice == "4":

            handle_config(cfg)

        elif choice == "5":

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

        formats = _ask_formats(cfg)

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

    if cfg.vad_filter and int(getattr(cfg, "batch_size", 0) or 0) > 0:

        info(f"Aceleración por lotes: batch_size={cfg.batch_size}")

    if not cfg.vad_filter:

        info("VAD desactivado (mejor para canciones/música).")

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

            update(seg.end, seg.text)

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
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
) -> None:
    """Descarga el audio del video y lo transcribe con faster-whisper."""

    import shutil
    import tempfile

    from stt.progress import youtube_download_progress

    tmp = Path(tempfile.mkdtemp(prefix="stt_yt_"))

    try:

        try:

            with youtube_download_progress() as dl:

                audio = download_audio(
                    video.url,
                    tmp,
                    on_progress=dl.on_progress,
                    should_cancel=dl.should_cancel,
                    cookies_from_browser=cookies_from_browser,
                    cookies_file=cookies_file,
                )

        except DownloadCancelled:

            warn("Descarga cancelada.")

            return

        except Exception as exc:  # noqa: BLE001

            msg = str(exc)

            lower = msg.lower()

            if "not a bot" in lower or "sign in" in lower:

                error(
                    "YouTube pide autenticación (anti-bot). "
                    "Abre youtube.com en tu navegador (sesión iniciada) y "
                    "reintenta con --cookies-from-browser chrome "
                    "(o safari / firefox). Si el navegador está abierto y "
                    "falla al leer cookies, ciérralo un momento o usa "
                    "--cookies archivo.txt."
                )

            elif "403" in lower or "forbidden" in lower:

                error(
                    "YouTube rechazó la descarga del audio (HTTP 403). "
                    "Suele ser anti-bot del CDN; reintenta con "
                    "--cookies-from-browser, actualiza yt-dlp "
                    "(pip install -U yt-dlp) o prueba otra red/VPN."
                )

            elif "timed out" in lower or "timeout" in lower:

                error(
                    "Timeout al descargar el audio desde el CDN de YouTube "
                    "(googlevideo). Suele ser red/ISP o VPN; reintenta más "
                    "tarde o prueba otra red."
                )

            raise

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


def _save_top_comments(
    cfg: Config,
    video: VideoRef,
    n: int,
) -> None:
    """Descarga y guarda los n comentarios más votados del video."""

    with console.status(
        f"[cyan]Obteniendo los {n} comentarios más votados…[/cyan]",
        spinner="dots",
    ):

        comments = fetch_top_comments(video.id, n)

    path = write_comments(
        comments,
        cfg.output,
        safe_filename(video.title),
        video.title,
    )

    if comments:

        info(f"{len(comments)} comentario(s) más votados → {path}")

    else:

        warn(f"Sin comentarios disponibles → {path}")


def _process_video(
    cfg: Config,
    video: VideoRef,
    languages: list[str],
    formats: list[str],
    timestamps: bool,
    use_whisper: bool,
    most_rated_comments: int | None = None,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
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

            if most_rated_comments is not None:

                _save_top_comments(cfg, video, most_rated_comments)

            return

        warn("Sin captions disponibles; usando Whisper como respaldo…")

    _whisper_youtube(
        cfg,
        video,
        formats,
        timestamps,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
    )

    if most_rated_comments is not None:

        _save_top_comments(cfg, video, most_rated_comments)


def handle_youtube(
    cfg: Config,
    url: str | None = None,
    formats: list[str] | None = None,
    timestamps: bool | None = None,
    use_whisper: bool = False,
    most_rated_comments: int | None = None,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
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

        formats = _ask_formats(cfg)

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

    if most_rated_comments is not None and most_rated_comments <= 0:

        error("--with-most-rated-comments requiere un entero positivo.")

        return

    if cookies_from_browser and cookies_file:

        error("Usa solo una de: --cookies-from-browser o --cookies.")

        return

    info(f"{len(videos)} video(s) a procesar.")

    if use_whisper:

        warn("Modo Whisper forzado: se ignoran los captions de YouTube.")

    if cookies_from_browser:

        info(f"Cookies del navegador: {cookies_from_browser}")

    elif cookies_file:

        info(f"Cookies desde archivo: {cookies_file}")

    if most_rated_comments is not None:

        info(
            f"También se guardarán los {most_rated_comments} "
            "comentarios más votados de cada video."
        )

    languages = _caption_languages(cfg)

    print()

    for video in videos:

        try:

            _process_video(
                cfg,
                video,
                languages,
                formats,
                timestamps,
                use_whisper,
                most_rated_comments=most_rated_comments,
                cookies_from_browser=cookies_from_browser,
                cookies_file=cookies_file,
            )

        except Exception as exc:  # noqa: BLE001

            error(f"Error con «{video.title}»: {exc}")


def _apply_voice(script, label: str, voice: str) -> None:
    """Fija la voz resuelta para una etiqueta en el guion y sus turnos."""

    script.voices[label] = voice

    for turn in script.turns:

        if turn.label == label:

            turn.voice = voice


def _resolve_say_voices(script) -> None:
    """Resuelve voces del motor say a su variante en el idioma del guion.

    Las voces multilingües (Reed, Eddy…) se leen en inglés si se pasan solo
    como "Reed"; hay que usar "Reed (Español (México))".
    """

    from stt.podcast import resolve_voice, DEFAULT_VOICES

    for label, voice in list(script.voices.items()):

        resolved = resolve_voice(voice, script.language)

        if resolved is None:

            resolved = resolve_voice(DEFAULT_VOICES[0], script.language) or DEFAULT_VOICES[0]

            warn(f"Voz «{voice}» no encontrada; uso «{resolved}» para {label}.")

        elif resolved != voice:

            warn(f"{label}: «{voice}» → «{resolved}» (variante en {script.language})")

        _apply_voice(script, label, resolved)


def _resolve_edge_voices(script) -> None:
    """Valida las voces neuronales de edge-tts (p. ej. es-MX-JorgeNeural)."""

    from stt.podcast import edge_voices, DEFAULT_EDGE_VOICES

    installed = edge_voices()

    default = DEFAULT_EDGE_VOICES[0]

    for label, voice in list(script.voices.items()):

        chosen = voice

        if installed and voice not in installed:

            warn(f"Voz edge «{voice}» no válida; uso «{default}» para {label}.")

            chosen = default

        _apply_voice(script, label, chosen)


def handle_podcast(
    cfg: Config,
    path: str | None = None,
    audio_format: str | None = None,
    rate: int | None = None,
) -> None:
    """Genera un podcast de audio a partir de un guion .md."""

    from stt.podcast import parse_script, synthesize, AUDIO_CODECS

    section("Podcast")

    if path is None:

        path = Prompt.ask("Ruta del guion (.md)").strip()

    script_path = expand_path(path)

    if not script_path.exists():

        error(f"El guion no existe: {script_path}")

        return

    try:

        script = parse_script(script_path)

    except Exception as exc:  # noqa: BLE001

        error(f"No se pudo leer el guion: {exc}")

        return

    if not script.turns:

        error(
            "El guion no tiene turnos de habla. Usa el formato "
            "'**ETIQUETA:** texto' y declara las voces en el front matter."
        )

        return

    fmt = (audio_format or "m4a").lower().lstrip(".")

    if fmt not in AUDIO_CODECS:

        error(f"Formato de audio no soportado: {fmt} (usa m4a, mp3 o wav)")

        return

    if script.engine == "edge":

        _resolve_edge_voices(script)

    else:

        _resolve_say_voices(script)

    info(f"Motor: {script.engine}")

    info(f"Título: {script.title}")

    info(f"Turnos: {len(script.turns)} · voces: " +
         ", ".join(f"{k}={v}" for k, v in script.voices.items()))

    print()

    try:

        with console.status(
            "[cyan]Sintetizando voces y uniendo el audio…[/cyan]",
            spinner="dots",
        ):

            out_path = synthesize(script, cfg.output, fmt=fmt, rate=rate)

    except Exception as exc:  # noqa: BLE001

        error(f"No se pudo generar el podcast: {exc}")

        return

    info(f"Podcast generado → {out_path}")


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
        f"Formatos ({', '.join(SUPPORTED_FORMATS)}; separados por coma)",
        default=", ".join(cfg.formats),
    )

    cfg.formats = [f.strip() for f in formats.split(",") if f.strip()]

    save_config(cfg)

    info("Configuración guardada.")


