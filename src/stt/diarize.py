"""Separación opcional de voces (entrevistas y podcasts).

No se importa al transcribir un solo hablante. PyTorch y pyannote
solo entran si el usuario lo pide y el dictamen del equipo lo permite.
"""

from __future__ import annotations

import gc
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from stt.hardware import (
    DIARIZE_MODEL_ID,
    diarization_verdict,
    format_diarization_verdict,
    huggingface_token,
    install_root,
    local_pipeline_dir,
    model_cache_dir,
    voices_cli,
    voices_package_installed,
)
from stt.segment import Segment


UNKNOWN_SPEAKER = "Desconocido"

_MODEL_PAGE = "https://huggingface.co/pyannote/speaker-diarization-community-1"


class DiarizeError(RuntimeError):
    """La separación de voces no pudo hacerse. El texto sí se puede guardar."""


@dataclass(slots=True)
class SpeakerTurn:

    start: float

    end: float

    speaker: str


@dataclass(slots=True)
class DiarizePlan:
    """Pedido ya aceptado: el extra cabe y el usuario quiere usarlo."""

    num_speakers: int | None

    names: list[str]


def parse_names(raw: str | None) -> list[str]:

    if not raw:

        return []

    return [part.strip() for part in raw.split(",") if part.strip()]


def _prepare_env() -> None:
    """Caché dentro del programa y sin telemetría de pyannote."""

    os.environ["PYANNOTE_METRICS_ENABLED"] = "false"

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    cache = model_cache_dir()

    cache.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("HF_HOME", str(cache))


def save_token(token: str) -> Path:

    path = install_root() / "config" / "hf_token"

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(token.strip() + "\n", encoding="utf8")

    try:

        path.chmod(0o600)

    except OSError:

        pass

    return path


def _confirm(question: str) -> bool:

    from rich.prompt import Prompt

    return Prompt.ask(question, choices=["s", "n"], default="n") == "s"


def _pip_install(args: list[str]) -> None:

    cmd = [sys.executable, "-m", "pip", "install", *args]

    try:

        subprocess.check_call(cmd)

    except FileNotFoundError:

        subprocess.check_call(
            ["uv", "pip", "install", "--python", sys.executable, *args]
        )


def install_voices_package() -> None:
    """Instala pyannote. En Windows y Linux, PyTorch de CPU (no la rueda CUDA)."""

    import importlib

    if sys.platform != "darwin":

        print()
        print("Instalando PyTorch, versión para procesador (sin tarjeta gráfica)…")
        print("Son unos cuantos gigas. La primera vez tarda.")
        print()

        _pip_install(
            [
                "torch>=2.8",
                "torchaudio>=2.8",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
            ]
        )

    print()
    print("Instalando la separación de voces…")
    print()

    _pip_install(["pyannote.audio>=4.0"])

    importlib.invalidate_caches()


def _model_source_ready() -> bool:

    return local_pipeline_dir() is not None or bool(huggingface_token())


def _explain_token() -> None:

    print()
    print("Para bajar el modelo la primera vez:")
    print(f"  1. Abra {_MODEL_PAGE}")
    print("  2. Acepte las condiciones (el modelo es gratis, con atribución).")
    print("  3. Cree un token de lectura en https://huggingface.co/settings/tokens")
    print("  4. Péguelo aquí, o guárdelo en la variable HF_TOKEN.")
    print("Después el audio no sale de esta computadora.")
    print()


def _ask_token() -> bool:

    _explain_token()

    token = input("Token de Hugging Face (Enter para omitir): ").strip()

    if not token:

        print("Sin token no se puede bajar el modelo.")

        return False

    path = save_token(token)

    print(f"Token guardado en {path} (no se sube a git).")

    return True


def enable_speakers(interactive: bool) -> bool:
    """Muestra el dictamen y, si cabe, deja el extra listo para usarse.

    No instala si el dictamen es negativo.
    """

    verdict = diarization_verdict()

    print()
    print(format_diarization_verdict(verdict))

    if not verdict.possible:

        return False

    if not verdict.installed:

        if not interactive:

            print(
                "El extra no está instalado. Desde la carpeta del programa: "
                + voices_cli("voces")
            )

            return False

        if not _confirm("¿Instalar ahora el extra de voces? Hace falta internet"):

            return False

        try:

            install_voices_package()

        except subprocess.CalledProcessError as exc:

            print(f"No se pudo instalar el extra (código {exc.returncode}).")

            return False

        if not voices_package_installed():

            print("El extra no quedó instalado.")

            return False

        print("Extra instalado.")

    if not _model_source_ready():

        if not interactive:

            _explain_token()

            return False

        if not _ask_token():

            return False

    return True


def run_voices() -> None:
    """Dictamen de este equipo y, si cabe, instalación del extra."""

    verdict = diarization_verdict()

    print()
    print(format_diarization_verdict(verdict))

    if not verdict.possible:

        return

    interactive = sys.stdin.isatty()

    if not verdict.installed:

        if not interactive:

            print(
                "Ejecute este comando en una ventana para confirmar la instalación: "
                + voices_cli("voces")
            )

            return

        if not _confirm("¿Instalar ahora el extra de voces? Hace falta internet"):

            print("No se instaló nada. La transcripción normal sigue igual.")

            return

        try:

            install_voices_package()

        except subprocess.CalledProcessError as exc:

            print(f"No se pudo instalar el extra (código {exc.returncode}).")

            return

        if not voices_package_installed():

            print("El extra no quedó instalado.")

            return

        print("Extra instalado.")

    if not _model_source_ready():

        if not interactive or not _ask_token():

            if interactive:

                print(
                    "Puede volver a ejecutar este comando cuando tenga el token: "
                    + voices_cli("voces")
                )

            else:

                _explain_token()

            return

    print()
    print("Comprobando que el modelo de voces abre en este equipo…")

    try:

        _prepare_env()

        pipeline = _load_pipeline()

        del pipeline

        gc.collect()

    except DiarizeError as exc:

        print(exc)

        return

    print("Modelo listo.")
    print("Para una entrevista, desde la carpeta del programa:")
    print("  " + voices_cli('entrevista.m4a --speakers 2 --names "Ana,Luis"'))
    print("Sin --speakers la transcripción no separa voces.")
    print()


def _load_pipeline():

    _prepare_env()

    try:

        from pyannote.audio import Pipeline

    except ImportError as exc:

        raise DiarizeError(
            "El extra de voces no está instalado. Desde la carpeta del programa: "
            + voices_cli("voces")
        ) from exc

    local = local_pipeline_dir()

    try:

        if local is not None:

            print(f"Modelo de voces local (sin descargar): {local}")

            return Pipeline.from_pretrained(str(local))

        token = huggingface_token()

        if not token:

            raise DiarizeError(
                "Falta el token de Hugging Face para bajar el modelo la primera vez. "
                "Ejecute: " + voices_cli("voces")
            )

        return Pipeline.from_pretrained(DIARIZE_MODEL_ID, token=token)

    except DiarizeError:

        raise

    except Exception as exc:

        raise DiarizeError(_explain_load_error(exc)) from exc


def _explain_load_error(exc: Exception) -> str:

    text = str(exc)

    lowered = text.lower()

    if any(word in lowered for word in ("403", "gated", "authorized", "token", "cannot access")):

        return (
            "No se pudo abrir el modelo de voces. "
            f"Acepte las condiciones en {_MODEL_PAGE} "
            "y revise el token (" + voices_cli("voces") + ").\n"
            f"Detalle: {text}"
        )

    return f"No se pudo abrir el modelo de voces.\nDetalle: {text}"


def _run_pipeline(pipeline, audio: Path, num_speakers: int | None):

    kwargs: dict = {}

    if num_speakers:

        kwargs["num_speakers"] = int(num_speakers)

    try:

        from pyannote.audio.pipelines.utils.hook import ProgressHook

    except ImportError:

        return pipeline(str(audio), **kwargs)

    try:

        with ProgressHook() as hook:

            return pipeline(str(audio), hook=hook, **kwargs)

    except TypeError:

        return pipeline(str(audio), **kwargs)


def _as_annotation(output, name: str):

    value = getattr(output, name, None)

    if value is None:

        return None

    if callable(value):

        try:

            value = value()

        except TypeError:

            return None

    return value


def _yield_turns(annotation):

    if hasattr(annotation, "itertracks"):

        for turn, _, speaker in annotation.itertracks(yield_label=True):

            yield float(turn.start), float(turn.end), str(speaker)

        return

    try:

        items = list(annotation)

    except TypeError:

        return

    for item in items:

        if not isinstance(item, tuple) or len(item) < 2:

            continue

        turn = item[0]

        speaker = item[-1]

        yield float(turn.start), float(turn.end), str(speaker)


def _iter_turns(output):
    """Prefiere los tramos exclusivos (un solo hablante por instante)."""

    candidates = [
        _as_annotation(output, "exclusive_speaker_diarization"),
        _as_annotation(output, "speaker_diarization"),
        output,
    ]

    for annotation in candidates:

        if annotation is None:

            continue

        turns = [
            (start, end, speaker)
            for start, end, speaker in _yield_turns(annotation)
            if end > start
        ]

        if turns:

            return turns

    return []


def _clip(audio: Path, minutes: float) -> Path:
    """Recorta los primeros N minutos a wav mono 16 kHz."""

    if shutil.which("ffmpeg") is None:

        raise DiarizeError("Falta ffmpeg para recortar el audio.")

    folder = Path(tempfile.mkdtemp(prefix="stt_voces_"))

    dest = folder / "clip.wav"

    seconds = float(minutes) * 60

    try:

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio),
                "-t",
                f"{seconds:.3f}",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-vn",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )

    except subprocess.CalledProcessError as exc:

        shutil.rmtree(folder, ignore_errors=True)

        detail = (exc.stderr or b"").decode("utf8", errors="replace")[-400:]

        raise DiarizeError(f"No se pudo recortar el audio.\n{detail}") from exc

    return dest


def diarize_audio(
    audio: Path,
    num_speakers: int | None = None,
    minutes: float | None = None,
) -> list[SpeakerTurn]:
    """Devuelve los tramos de cada voz. Libera el modelo al terminar."""

    clip_dir: Path | None = None

    work = audio

    pipeline = None

    try:

        if minutes:

            work = _clip(audio, minutes)

            clip_dir = work.parent

        pipeline = _load_pipeline()

        output = _run_pipeline(pipeline, work, num_speakers)

        raw_turns = _iter_turns(output)

        del output

    except DiarizeError:

        raise

    except Exception as exc:

        raise DiarizeError(_explain_load_error(exc)) from exc

    finally:

        if pipeline is not None:

            del pipeline

        gc.collect()

        if clip_dir is not None:

            shutil.rmtree(clip_dir, ignore_errors=True)

    return [
        SpeakerTurn(start=start, end=end, speaker=speaker)
        for start, end, speaker in raw_turns
    ]


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> None:
    """Cada frase se queda con la voz cuyo tramo se solapa más."""

    for segment in segments:

        best_label: str | None = None

        best_overlap = 0.0

        best_start = 0.0

        for turn in turns:

            overlap = min(segment.end, turn.end) - max(segment.start, turn.start)

            if overlap < 0.05:

                continue

            if overlap > best_overlap or (
                overlap == best_overlap and turn.start < best_start
            ):

                best_overlap = overlap

                best_label = turn.speaker

                best_start = turn.start

        segment.speaker = best_label or UNKNOWN_SPEAKER


def apply_names(
    segments: list[Segment],
    names: list[str],
) -> tuple[list[str], str | None]:
    """Cambia SPEAKER_00 por el nombre, o por Hablante N, en orden de aparición."""

    order: list[str] = []

    for segment in segments:

        raw = segment.speaker

        if not raw or raw == UNKNOWN_SPEAKER or raw in order:

            continue

        order.append(raw)

    mapping = {
        raw: names[index] if index < len(names) else f"Hablante {index + 1}"
        for index, raw in enumerate(order)
    }

    for segment in segments:

        if segment.speaker in mapping:

            segment.speaker = mapping[segment.speaker]

    labels = [mapping[raw] for raw in order]

    note = None

    heard = len(order)

    if names and heard and len(names) > heard:

        note = (
            f"Se oyeron {heard} voces y dio {len(names)} nombres. "
            "Los que sobran no se usan."
        )

    elif names and heard and len(names) < heard:

        note = (
            f"Se oyeron {heard} voces y dio {len(names)} nombres. "
            "El resto queda como Hablante N."
        )

    return labels, note
