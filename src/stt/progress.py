from __future__ import annotations

from collections import deque
from contextlib import contextmanager

from rich.console import Group
from rich.live import Live
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from stt.formatter import console

# Líneas de vista previa bajo la barra (poca altura para no taparla).
_PREVIEW_LINES = 3
_PREVIEW_PAD = "…"


def _clip(text: str, width: int) -> str:
    """Una sola línea, recortada al ancho de la terminal."""

    cleaned = " ".join(text.split())

    if width < 8:

        return cleaned

    if len(cleaned) <= width:

        return cleaned

    return cleaned[: width - 1] + "…"


@contextmanager
def transcription_progress(total_seconds: float):
    """Barra de progreso + vista previa del texto que se va generando.

    Entrega ``update(current_seconds, text=None)``. La barra se mantiene fija;
    debajo se muestran hasta 3 líneas del último texto (estado estable +
    actividad actual, al estilo de logs en Docker).
    """

    columns = [
        TextColumn("[cyan]Transcribiendo[/cyan]"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("restante"),
        TimeRemainingColumn(),
    ]

    total = max(float(total_seconds or 0.0), 0.001)

    recent: deque[str] = deque(maxlen=_PREVIEW_LINES)

    progress = Progress(*columns, console=console)

    task = progress.add_task("stt", total=total)

    def _render() -> Group:

        # Ancho útil: deja margen para que no envuelva y empuje la barra.
        width = max((console.width or 80) - 2, 20)

        lines = list(recent)

        while len(lines) < _PREVIEW_LINES:

            lines.append(_PREVIEW_PAD if not recent else "")

        preview = Text()

        for i, line in enumerate(lines):

            if line:

                preview.append(_clip(line, width), style="dim")

            if i < len(lines) - 1:

                preview.append("\n")

        return Group(progress, preview)

    with Live(
        _render(),
        console=console,
        refresh_per_second=10,
        vertical_overflow="crop",
    ) as live:

        def update(
            current_seconds: float,
            text: str | None = None,
        ) -> None:

            progress.update(
                task,
                completed=min(float(current_seconds), total),
            )

            if text is not None:

                cleaned = " ".join(text.split())

                if cleaned:

                    recent.append(cleaned)

            live.update(_render())

        yield update

        progress.update(task, completed=total)

        live.update(_render())
