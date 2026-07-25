import argparse

from stt.config import load_config
from stt.cli import run_menu, handle_local, handle_youtube, handle_podcast


def main():

    cfg = load_config()

    parser = argparse.ArgumentParser(
        prog="stt",
        description="Speech To Text (Faster Whisper)",
    )

    parser.add_argument(
        "source",
        nargs="?",
        help="Ruta de un archivo local, URL de YouTube, 'youtube', o vacío para el menú",
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="URL de YouTube (cuando source es 'youtube')",
    )

    parser.add_argument(
        "-f", "--format",
        dest="formats",
        help="Formato(s) de salida: txt, md, srt, vtt, json (coma para varios)",
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

    args = parser.parse_args()

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

        handle_podcast(cfg, args.url, audio_format=audio_format, rate=args.rate)

    elif args.source == "youtube":

        handle_youtube(
            cfg,
            args.url,
            formats=formats,
            timestamps=timestamps,
            use_whisper=args.whisper,
        )

    elif _is_youtube_url(args.source):

        handle_youtube(
            cfg,
            args.source,
            formats=formats,
            timestamps=timestamps,
            use_whisper=args.whisper,
        )

    else:

        handle_local(
            cfg,
            args.source,
            formats=formats,
            timestamps=timestamps,
            minutes=args.minutes,
        )


def _is_youtube_url(text: str) -> bool:

    lowered = text.lower()

    return lowered.startswith(("http://", "https://")) and (
        "youtube.com" in lowered or "youtu.be" in lowered
    )
