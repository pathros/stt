from __future__ import annotations

from pathlib import Path
from typing import Iterator

from stt.segment import Segment


_MODEL_CACHE: dict[tuple[str, str], object] = {}

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


def _is_hallucination(text: str) -> bool:
    """Detecta frases típicas de alucinación de Whisper (créditos, outros)."""

    lowered = text.strip().lower()

    if not lowered:

        return True

    return any(phrase in lowered for phrase in _HALLUCINATION_PHRASES)


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

    Con ``vad_filter=False`` (recomendado para canciones/música) también
    desactiva ``condition_on_previous_text`` para evitar alucinaciones
    típicas ("Субтитры сделал…", "Thanks for watching", etc.).
    """

    model = _get_model(cfg)

    language = None if cfg.language == "auto" else cfg.language

    clip = "0"

    if minutes:

        clip = f"0,{float(minutes) * 60:.3f}"

    # En música el VAD suele tirar casi todo el audio; sin VAD, no
    # condicionar en el texto previo evita bucles de alucinación.
    condition_prev = cfg.vad_filter

    # Guía suave de estilo (puntuación / mayúsculas) cuando el idioma es ES.
    # Whisper ya puntúa de fábrica; esto reduce salidas “planas” en dictados.
    initial_prompt = getattr(cfg, "initial_prompt", "") or None

    if not initial_prompt and language == "es":

        initial_prompt = (
            "Transcripción en español con puntuación, comas y "
            "mayúsculas correctas."
        )

    raw_segments, info = model.transcribe(
        str(audio),
        language=language,
        beam_size=cfg.beam_size,
        vad_filter=cfg.vad_filter,
        condition_on_previous_text=condition_prev,
        clip_timestamps=clip,
        initial_prompt=initial_prompt,
    )

    def generator() -> Iterator[Segment]:

        for s in raw_segments:

            text = (s.text or "").strip()

            if not text or _is_hallucination(text):

                continue

            yield Segment(start=s.start, end=s.end, text=s.text)

    return info, generator()
