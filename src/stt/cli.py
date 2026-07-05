from pathlib import Path

from rich.prompt import Prompt

from stt.formatter import (
    banner,
    show_config,
    error,
)


def run(cfg):

    banner()

    show_config(cfg)

    print()

    filename = Prompt.ask(
        "Ruta del archivo"
    ).strip()

    audio = Path(filename).expanduser()

    if not audio.exists():

        error("El archivo no existe.")

        return

    print()

    print(audio)
