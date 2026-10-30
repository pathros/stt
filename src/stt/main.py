import argparse

from stt.config import load_config
from stt.cli import run_menu, handle_local, handle_youtube, handle_podcast
from stt.youtube import DEFAULT_MOST_RATED_COMMENTS


def main():

    parser = argparse.ArgumentParser(
        prog="stt",
        description="Speech To Text (Faster Whisper)",
    )

    parser.add_argument(
        "source",
        nargs="?",
        help=(
            "Archivo local, URL de YouTube, 'youtube', 'podcast', "
            "'voces' o vacío para el menú"
        ),
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="URL de YouTube (cuando source es 'youtube')",
    )

    parser.add_argument(
        "-f", "--format",
        dest="formats",
        help="Formato(s) de salida: txt, md, docx, srt, vtt, json (coma para varios)",
    )

    ts = parser.add_mutually_exclusive_group()

    ts.add_argument(
        "-t", "--timestamps",
        dest="timestamps",
        action="store_true",
        default=None,
        help="Incluir marcas de tiempo",
    )

    ts.add_argument(
        "--no-timestamps",
        dest="timestamps",
        action="store_false",
        help="Sin marcas de tiempo",
    )

    parser.add_argument(
        "-m", "--model",
        help="Sobrescribe el modelo (p. ej. large-v3, medium, tiny)",
    )

    parser.add_argument(
        "-l", "--language",
        help="Idioma del audio (p. ej. es) o 'auto'",
    )

    parser.add_argument(
        "-o", "--output",
        help="Carpeta de salida",
    )

    parser.add_argument(
        "--minutes",
        type=float,
        help="Vista previa: transcribe solo los primeros N minutos",
    )

    parser.add_argument(
        "--whisper",
        action="store_true",
        help="En YouTube, forzar transcripción con Whisper (ignora captions)",
    )

    parser.add_argument(
        "--with-most-rated-comments",
        nargs="?",
        const=DEFAULT_MOST_RATED_COMMENTS,
        default=None,
        type=int,
        metavar="N",
        help=(
            "YouTube: guardar los N comentarios con más likes por video "
            f"(default: {DEFAULT_MOST_RATED_COMMENTS}; también en playlists)"
        ),
    )

    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        help=(
            "YouTube: cookies del navegador para anti-bot "
            "(chrome, safari, firefox, brave, …)"
        ),
    )

    parser.add_argument(
        "--cookies",
        metavar="FILE",
        help="YouTube: archivo Netscape de cookies (alternativa al navegador)",
    )

    parser.add_argument(
        "--no-vad",
        dest="vad_filter",
        action="store_false",
        default=None,
        help="Desactiva el filtro VAD (recomendado para canciones/música)",
    )

    parser.add_argument(
        "--rate",
        type=int,
        help="Podcast: velocidad de voz en palabras por minuto (p. ej. 180)",
    )

    parser.add_argument(
        "--speakers",
        nargs="?",
        const=0,
        type=int,
        default=None,
        metavar="N",
        help=(
            "Separa quién habla (opcional; no viene instalado). "
            "Sin número, estima cuántas personas hay. "
            "Entrevista: --speakers 2"
        ),
    )

    parser.add_argument(
        "--names",
        help='Nombres en el orden en que hablan, separados por coma. Ej. "Ana,Luis"',
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="Con «configurar»: Word, Descargas y modelo según la memoria, sin preguntas",
    )

    args = parser.parse_args()

    if args.source in {"configurar", "setup"}:

        from stt.setup_wizard import run_setup

        run_setup(auto=args.auto)

        return

    if args.source == "voces":

        from stt.diarize import run_voices

        run_voices()

        return

    if args.names and args.speakers is None:

        parser.error("--names solo aplica junto con --speakers")

    if args.speakers is not None and not 0 <= args.speakers <= 20:

        parser.error("--speakers admite de 1 a 20, o sin número para estimarlo")

    cfg = load_config()

    # Overrides de configuración vía flags.
    if args.model:

        cfg.model = args.model

    if args.language:

        cfg.language = args.language

    if args.output:

        from stt.utils import expand_path

        cfg.output = expand_path(args.output)

    if args.vad_filter is not None:

        cfg.vad_filter = args.vad_filter

    formats = None

    if args.formats:

        formats = [f.strip() for f in args.formats.split(",") if f.strip()]

    # En comando directo con formato dado, no preguntamos marcas.
    timestamps = args.timestamps

    if timestamps is None and formats is not None:

        timestamps = False

    # Híbrido: sin argumentos -> menú guiado; con argumentos -> directo.
    if args.source is None:

        run_menu(cfg)

    elif args.source == "podcast":

        audio_format = formats[0] if formats else None

        if args.speakers is not None:

            print(
                "El podcast parte de un guion: las voces ya van escritas. "
                "--speakers no aplica."
            )

        handle_podcast(cfg, args.url, audio_format=audio_format, rate=args.rate)

    elif args.source == "youtube":

        handle_youtube(
            cfg,
            args.url,
            formats=formats,
            timestamps=timestamps,
            use_whisper=args.whisper,
            most_rated_comments=args.with_most_rated_comments,
            cookies_from_browser=args.cookies_from_browser,
            cookies_file=args.cookies,
            speakers=args.speakers,
            names=args.names,
        )

    elif _is_youtube_url(args.source):

        handle_youtube(
            cfg,
            args.source,
            formats=formats,
            timestamps=timestamps,
            use_whisper=args.whisper,
            most_rated_comments=args.with_most_rated_comments,
            cookies_from_browser=args.cookies_from_browser,
            cookies_file=args.cookies,
            speakers=args.speakers,
            names=args.names,
        )

    else:

        handle_local(
            cfg,
            args.source,
            formats=formats,
            timestamps=timestamps,
            minutes=args.minutes,
            speakers=args.speakers,
            names=args.names,
        )


def _is_youtube_url(text: str) -> bool:

    lowered = text.lower()

    return lowered.startswith(("http://", "https://")) and (
        "youtube.com" in lowered or "youtu.be" in lowered
    )
