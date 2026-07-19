from __future__ import annotations

from contextlib import contextmanager

from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from stt.formatter import console


@contextmanager
def transcription_progress(total_seconds: float):
    """Barra de progreso basada en la duración del audio.

    Entrega una función `update(current_seconds)` para avanzar la barra
    conforme se van produciendo segmentos.
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

    with Progress(*columns, console=console) as progress:

        task = progress.add_task("stt", total=total)

        def update(current_seconds: float) -> None:

            progress.update(task, completed=min(float(current_seconds), total))

        yield update

        progress.update(task, completed=total)
