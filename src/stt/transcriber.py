from __future__ import annotations

from pathlib import Path
from typing import Iterator

from stt.segment import Segment


_MODEL_CACHE: dict[tuple[str, str], object] = {}


def _get_model(cfg):
    """Carga (y cachea) el modelo de faster-whisper en CPU."""

    import os

    from faster_whisper import WhisperModel

    key = (cfg.model, cfg.compute_type)

    if key not in _MODEL_CACHE:

        _MODEL_CACHE[key] = WhisperModel(
            cfg.model,
            device="cpu",
            compute_type=cfg.compute_type,
            cpu_threads=os.cpu_count() or 4,
        )

    return _MODEL_CACHE[key]


def transcribe(
    audio: Path,
    cfg,
    minutes: float | None = None,
):
    """Transcribe un archivo de audio con faster-whisper.

    Devuelve (info, generador_de_Segment). El generador se debe
    consumir para obtener los segmentos (permite mostrar progreso).

    `minutes`: si se indica, solo transcribe los primeros N minutos
    (vista previa) usando clip_timestamps.
    """

    model = _get_model(cfg)

    language = None if cfg.language == "auto" else cfg.language

    clip = "0"

    if minutes:

        clip = f"0,{float(minutes) * 60:.3f}"

    raw_segments, info = model.transcribe(
        str(audio),
        language=language,
        beam_size=cfg.beam_size,
        vad_filter=cfg.vad_filter,
        clip_timestamps=clip,
    )

    def generator() -> Iterator[Segment]:

        for s in raw_segments:

            yield Segment(start=s.start, end=s.end, text=s.text)

    return info, generator()
