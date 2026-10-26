from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from stt.segment import Segment


_MODEL_CACHE: dict[tuple[str, str, int], object] = {}

# Marcas de agua / créditos que Whisper inventa con frecuencia en música.
_HALLUCINATION_PHRASES = (
    "субтитры сделал dimatorzok",
    "субтитры создавал dimatorzok",
    "субтитры сделал",
    "dimatorzok",
    "subtitles by",
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "подписывайтесь",
)

_SAMPLE_RATE = 16_000


def _is_hallucination(text: str) -> bool:
    """Detecta frases típicas de alucinación de Whisper (créditos, outros)."""

    lowered = text.strip().lower()

    if not lowered:

        return True

    return any(phrase in lowered for phrase in _HALLUCINATION_PHRASES)


def _cpu_threads() -> int:
    """Hilos para CTranslate2.

    En CPUs híbridos (p. ej. i5-14500 con 20 lógicos) saturar todos suele
    ir peor que usar un tope razonable (~8).
    """

    n = os.cpu_count() or 4

    if n >= 12:

        return 8

    return max(4, n)


def _compat_audio_open() -> None:
    """PyAV 19 ya no acepta metadata_errors; faster-whisper 1.2.1 todavía lo manda."""

    import faster_whisper.audio as audio

    original = audio.av.open

    if getattr(original, "_stt_wrapped", False):

        return

    def open_compat(*args, **kwargs):

        kwargs.pop("metadata_errors", None)

        kwargs.pop("metadata_encoding", None)

        return original(*args, **kwargs)

    open_compat._stt_wrapped = True

    audio.av.open = open_compat


def _model_candidates(cfg) -> list[Path]:

    from stt.config import CONFIG_PATH

    found: list[Path] = []

    explicit = (getattr(cfg, "model_path", "") or "").strip()

    if explicit:

        found.append(Path(explicit).expanduser())

    env = os.environ.get("STT_MODEL_PATH", "").strip()

    if env:

        found.append(Path(env).expanduser())

    root = CONFIG_PATH.parents[1]

    found.append(root / "models" / cfg.model)

    return found


def _local_model(cfg) -> str | None:
    """Carpeta ya descargada (proyecto o USB), si trae model.bin."""

    for path in _model_candidates(cfg):

        if (path / "model.bin").is_file():

            return str(path)

    return None


def _download_model(name: str, attempts: int = 3) -> None:
    """Baja el modelo con reintentos. Si ya está en caché, sale enseguida."""

    import time

    from faster_whisper.utils import download_model

    last: Exception | None = None

    for attempt in range(1, attempts + 1):

        try:

            download_model(name)

            return

        except Exception as exc:  # noqa: BLE001

            last = exc

            print(
                f"No se pudo descargar el modelo "
                f"(intento {attempt} de {attempts}): {exc}"
            )

            if attempt < attempts:

                print("Se reintenta en unos segundos…")

                time.sleep(3 * attempt)

    raise SystemExit(
        "No se pudo descargar el modelo de transcripción.\n"
        "Revise la conexión y vuelva a arrastrar el audio, "
        "o copie la carpeta models\\medium desde la USB.\n"
        f"Detalle: {last}"
    )


def _get_model(cfg):
    """Carga (y cachea) el modelo de faster-whisper en CPU."""

    from faster_whisper import WhisperModel

    _compat_audio_open()

    threads = _cpu_threads()

    local = _local_model(cfg)

    model_id = local or cfg.model

    if local is None:

        _download_model(cfg.model)

    else:

        print(f"Modelo local (sin descargar): {local}")

    key = (model_id, cfg.compute_type, threads)

    if key not in _MODEL_CACHE:

        _MODEL_CACHE[key] = WhisperModel(
            model_id,
            device="cpu",
            compute_type=cfg.compute_type,
            cpu_threads=threads,
            num_workers=1,
            local_files_only=local is not None,
        )

    return _MODEL_CACHE[key]


def _initial_prompt(cfg, language: str | None) -> str | None:
    """Guía suave de estilo; vacío en config = default solo para español."""

    prompt = getattr(cfg, "initial_prompt", "") or None

    if prompt:

        return prompt

    if language == "es":

        return (
            "Transcripción en español con puntuación, comas y "
            "mayúsculas correctas."
        )

    return None


def _segment_generator(raw_segments) -> Iterator[Segment]:

    for s in raw_segments:

        text = (s.text or "").strip()

        if not text or _is_hallucination(text):

            continue

        yield Segment(start=s.start, end=s.end, text=s.text)


def transcribe(
    audio: Path,
    cfg,
    minutes: float | None = None,
):
    """Transcribe un archivo de audio con faster-whisper.

    Devuelve (info, generador_de_Segment). El generador se debe
    consumir para obtener los segmentos (permite mostrar progreso).

    `minutes`: si se indica, solo transcribe los primeros N minutos
    (vista previa).

    Con VAD activado usa inferencia por lotes (más rápida en CPU) si
    ``batch_size`` > 0. Con ``--no-vad`` (canciones) usa el camino
    secuencial: el batch exige VAD o clips explícitos.

    ``condition_on_previous_text`` va en False para evitar bucles donde
    se repite la misma línea aunque el audio ya cambió.
    """

    model = _get_model(cfg)

    language = None if cfg.language == "auto" else cfg.language

    prompt = _initial_prompt(cfg, language)

    batch_size = int(getattr(cfg, "batch_size", 8) or 0)

    # Batch + VAD = camino rápido para habla/reuniones.
    # Sin VAD (música) → secuencial.
    use_batch = bool(cfg.vad_filter and batch_size > 0)

    if use_batch:

        from faster_whisper import BatchedInferencePipeline

        pipeline = BatchedInferencePipeline(model=model)

        clip_timestamps = None

        if minutes:

            # Muestras a 16 kHz (formato que espera el pipeline por lotes).
            end = int(float(minutes) * 60 * _SAMPLE_RATE)

            clip_timestamps = [{"start": 0, "end": max(end, 1)}]

        raw_segments, info = pipeline.transcribe(
            str(audio),
            language=language,
            beam_size=cfg.beam_size,
            best_of=1,
            vad_filter=clip_timestamps is None,
            condition_on_previous_text=False,
            initial_prompt=prompt,
            batch_size=batch_size,
            clip_timestamps=clip_timestamps,
            without_timestamps=False,
        )

    else:

        clip = "0"

        if minutes:

            clip = f"0,{float(minutes) * 60:.3f}"

        raw_segments, info = model.transcribe(
            str(audio),
            language=language,
            beam_size=cfg.beam_size,
            best_of=1,
            vad_filter=cfg.vad_filter,
            condition_on_previous_text=False,
            clip_timestamps=clip,
            initial_prompt=prompt,
        )

    return info, _segment_generator(raw_segments)
