from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
import select
import sys
import threading

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
_CANCEL_KEY = "x"


def _clip(text: str, width: int) -> str:
    """Una sola línea, recortada al ancho de la terminal."""

    cleaned = " ".join(text.split())

    if width < 8:

        return cleaned

    if len(cleaned) <= width:

        return cleaned

    return cleaned[: width - 1] + "…"


class _CancelKeyWatcher:
    """Detecta una tecla de cancelación en stdin sin bloquear (TTY)."""

    def __init__(self, key: str = _CANCEL_KEY) -> None:

        self.key = key.lower()

        self.cancelled = False

        self._stop = threading.Event()

        self._thread: threading.Thread | None = None

        self._old_attrs = None

        self._fd: int | None = None

    def __enter__(self) -> "_CancelKeyWatcher":

        if not sys.stdin.isatty():

            return self

        if sys.platform == "win32":

            self._thread = threading.Thread(
                target=self._loop_windows,
                daemon=True,
            )

            self._thread.start()

            return self

        import termios
        import tty

        try:

            self._fd = sys.stdin.fileno()

            self._old_attrs = termios.tcgetattr(self._fd)

            tty.setcbreak(self._fd)

        except (termios.error, OSError, ValueError):

            self._fd = None

            self._old_attrs = None

            return self

        self._thread = threading.Thread(
            target=self._loop_posix,
            daemon=True,
        )

        self._thread.start()

        return self

    def __exit__(self, *args) -> None:

        self._stop.set()

        if self._thread is not None:

            self._thread.join(timeout=0.5)

        if self._old_attrs is not None and self._fd is not None:

            import termios

            try:

                termios.tcsetattr(
                    self._fd,
                    termios.TCSADRAIN,
                    self._old_attrs,
                )

            except (termios.error, OSError):

                pass

    def _loop_posix(self) -> None:

        assert self._fd is not None

        while not self._stop.is_set():

            try:

                ready, _, _ = select.select([self._fd], [], [], 0.15)

            except (OSError, ValueError):

                break

            if not ready:

                continue

            try:

                ch = sys.stdin.read(1)

            except OSError:

                break

            if ch and ch.lower() == self.key:

                self.cancelled = True

                break

    def _loop_windows(self) -> None:

        import msvcrt

        while not self._stop.is_set():

            if msvcrt.kbhit():

                ch = msvcrt.getwch()

                if ch and ch.lower() == self.key:

                    self.cancelled = True

                    break

            self._stop.wait(0.15)


@dataclass(slots=True)
class DownloadProgress:
    """Callbacks para ``download_audio`` durante la UI de descarga."""

    on_progress: Callable[[dict], None]

    should_cancel: Callable[[], bool]


@contextmanager
def youtube_download_progress():
    """UI de descarga YouTube: espera → % → cancelación con tecla x.

    Entrega un ``DownloadProgress`` con ``on_progress`` (hook yt-dlp) y
    ``should_cancel`` (bool). Antes de que empiece la transferencia muestra
    un mensaje de espera; al iniciar, el porcentaje.
    """

    state = {
        "started": False,
        "percent": 0.0,
        "cancel_requested": False,
        "extracting": False,
    }

    def _render() -> Text:

        hint = f'[dim](presiona "{_CANCEL_KEY}" para cancelar)[/dim]'

        if state["cancel_requested"]:

            return Text.from_markup(
                "[yellow]Cancelación solicitada…[/yellow] "
                "[dim]se detendrá en cuanto sea posible[/dim]"
            )

        if state["extracting"]:

            return Text.from_markup(
                "[cyan]Extrayendo audio (ffmpeg)…[/cyan]  " + hint
            )

        if state["started"]:

            pct = state["percent"]

            return Text.from_markup(
                f"[cyan]Descargando audio…[/cyan] "
                f"[bold]{pct:>3.0f}%[/bold]  {hint}"
            )

        return Text.from_markup(
            "[cyan]Esperando a que inicie la descarga…[/cyan]  " + hint
        )

    with _CancelKeyWatcher(_CANCEL_KEY) as watcher:

        with Live(
            _render(),
            console=console,
            refresh_per_second=8,
            transient=True,
        ) as live:

            def _refresh() -> None:

                if watcher.cancelled:

                    state["cancel_requested"] = True

                live.update(_render())

            def should_cancel() -> bool:

                if watcher.cancelled:

                    state["cancel_requested"] = True

                    _refresh()

                    return True

                return False

            def on_progress(d: dict) -> None:

                # La cancelación la lanza download_audio vía should_cancel.
                if should_cancel():

                    return

                status = d.get("status")

                if status == "downloading":

                    state["started"] = True

                    state["extracting"] = False

                    total = d.get("total_bytes") or d.get(
                        "total_bytes_estimate"
                    )

                    done = d.get("downloaded_bytes") or 0

                    if total:

                        state["percent"] = max(
                            0.0,
                            min(100.0, 100.0 * float(done) / float(total)),
                        )

                    elif "_percent_str" in d:

                        raw = str(d["_percent_str"]).strip().rstrip("%")

                        try:

                            state["percent"] = float(raw)

                        except ValueError:

                            pass

                elif status == "finished":

                    state["started"] = True

                    state["percent"] = 100.0

                    state["extracting"] = True

                _refresh()

            # Refresco periódico por si cancelan en la fase de espera
            # (aún sin hooks de progreso de yt-dlp).
            stop_pulse = threading.Event()

            def _pulse() -> None:

                while not stop_pulse.wait(0.2):

                    _refresh()

            pulser = threading.Thread(target=_pulse, daemon=True)

            pulser.start()

            try:

                yield DownloadProgress(
                    on_progress=on_progress,
                    should_cancel=should_cancel,
                )

            finally:

                stop_pulse.set()

                pulser.join(timeout=0.5)


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
