from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

from stt.utils import safe_filename


# Voces por defecto según el motor, si el guion no las declara.
DEFAULT_VOICES = ("Paulina", "Reed")                       # motor say (macOS)

DEFAULT_EDGE_VOICES = ("es-MX-DaliaNeural", "es-MX-JorgeNeural")  # motor edge

SAMPLE_RATE = 22050


def default_voices(engine: str) -> tuple[str, ...]:

    return DEFAULT_EDGE_VOICES if engine == "edge" else DEFAULT_VOICES

AUDIO_CODECS = {
    "m4a": ["-c:a", "aac", "-b:a", "128k"],
    "mp3": ["-c:a", "libmp3lame", "-q:a", "4"],
    "wav": ["-c:a", "pcm_s16le"],
}


@dataclass(slots=True)
class Turn:
    """Un turno de habla del guion."""

    label: str

    voice: str

    text: str


@dataclass(slots=True)
class PodcastScript:
    """Guion de podcast ya analizado."""

    title: str

    language: str

    voices: dict[str, str]

    pause: float

    turns: list[Turn]

    engine: str = "say"


# --------------------------------------------------------------------------- #
# Análisis del guion (.md)
# --------------------------------------------------------------------------- #

def _split_front_matter(raw: str) -> tuple[dict, str]:
    """Separa el front matter YAML (entre --- ... ---) del cuerpo."""

    if raw.lstrip().startswith("---"):

        raw = raw.lstrip()

        parts = raw.split("---", 2)

        if len(parts) >= 3:

            meta = yaml.safe_load(parts[1]) or {}

            if isinstance(meta, dict):

                return meta, parts[2]

    return {}, raw


def _strip_markdown(text: str) -> str:
    """Limpia marcas de markdown para que no se lean en voz alta."""

    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)          # imágenes

    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)       # enlaces -> texto

    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text)             # encabezados

    text = re.sub(r"^\s*>\s?", "", text)                      # citas

    text = re.sub(r"[*_`~]+", "", text)                       # énfasis/código

    return re.sub(r"\s+", " ", text).strip()


def _match_speaker(line: str, labels: set[str]) -> tuple[str, str] | None:
    """Detecta un cambio de hablante SOLO si la etiqueta está declarada.

    Acepta: `**ANA:** ...`, `ANA: ...`, `[ANA] ...`
    """

    s = line.strip()

    # Forma [ANA] resto
    m = re.match(r"^\[\s*([^\]]+?)\s*\]\s*:?\s*(.*)$", s)

    if m and m.group(1).strip().upper() in labels:

        return m.group(1).strip().upper(), m.group(2)

    # Forma **ANA:** resto  /  **ANA**: resto  /  ANA: resto
    m = re.match(r"^\*{0,2}\s*([^:*\[\]]+?)\s*\*{0,2}\s*:\s*\*{0,2}\s*(.*)$", s)

    if m and m.group(1).strip().upper() in labels:

        return m.group(1).strip().upper(), m.group(2)

    return None


def parse_script(path: Path) -> PodcastScript:
    """Analiza un guion .md y devuelve un PodcastScript."""

    raw = path.read_text(encoding="utf8")

    meta, body = _split_front_matter(raw)

    title = str(meta.get("title") or path.stem)

    language = str(meta.get("language") or "es-MX")

    pause = float(meta.get("pause", 0.4))

    engine = str(meta.get("engine") or "say").lower()

    # Acepta varias formas en el front matter:
    #   voice: Paulina                       -> monólogo (una sola voz)
    #   voices: {ANA: Paulina, LUIS: Reed}
    #   speakers: [{name: ANA, voice: Paulina}, {name: LUIS, voice: Reed}]
    voices_meta = meta.get("voices")

    if not voices_meta and isinstance(meta.get("speakers"), list):

        voices_meta = {}

        for sp in meta["speakers"]:

            if isinstance(sp, dict) and sp.get("name"):

                voices_meta[sp["name"]] = sp.get("voice", "")

    # `speaker:` (singular) para guiones de monólogo.
    if not voices_meta and isinstance(meta.get("speaker"), dict):

        sp = meta["speaker"]

        if sp.get("name"):

            voices_meta = {sp["name"]: sp.get("voice", "")}

    voices = {str(k).upper(): str(v) for k, v in (voices_meta or {}).items()}

    # Monólogo: `voice:` escalar, o ninguna voz declarada.
    if not voices:

        scalar = meta.get("voice")

        voices = {"NARRADOR": str(scalar) if scalar else ""}

    labels = set(voices.keys())

    # En modo de una sola voz, todo el texto se atribuye a esa voz aunque
    # no lleve etiquetas **NOMBRE:** delante.
    default_label: str | None = next(iter(voices)) if len(voices) == 1 else None

    turns: list[Turn] = []

    current_label: str | None = default_label

    current_lines: list[str] = []

    def flush() -> None:

        nonlocal current_label, current_lines

        if current_label and current_lines:

            text = _strip_markdown(" ".join(current_lines))

            if text:

                voice = voices.get(current_label, "")

                turns.append(Turn(current_label, voice, text))

        current_lines = []

    for line in body.splitlines():

        stripped = line.strip()

        if not stripped:

            continue

        # Separadores, encabezados y pausas cierran el turno actual
        # (evita que su texto se pegue al hablante anterior).
        if (
            stripped == "---"
            or stripped.startswith("#")
            or stripped.lower() in ("[pausa]", "[pause]")
        ):

            flush()

            current_label = default_label

            continue

        match = _match_speaker(line, labels)

        if match:

            flush()

            current_label, rest = match

            current_lines = [rest] if rest else []

        elif current_label:

            current_lines.append(stripped)

    flush()

    _assign_missing_voices(turns, voices, engine)

    return PodcastScript(
        title=title,
        language=language,
        voices=voices,
        pause=pause,
        turns=turns,
        engine=engine,
    )


def _assign_missing_voices(
    turns: list[Turn],
    voices: dict[str, str],
    engine: str = "say",
) -> None:
    """Asigna una voz por defecto a etiquetas sin voz declarada."""

    defaults = default_voices(engine)

    order: list[str] = []

    for t in turns:

        if t.label not in order:

            order.append(t.label)

    for i, label in enumerate(order):

        if not voices.get(label):

            voices[label] = defaults[i % len(defaults)]

    for t in turns:

        if not t.voice:

            t.voice = voices[t.label]


def edge_voices() -> set[str]:
    """Nombres cortos de las voces de edge-tts (p. ej. es-MX-JorgeNeural)."""

    try:

        import asyncio

        import edge_tts

        data = asyncio.run(edge_tts.list_voices())

        return {v["ShortName"] for v in data}

    except Exception:  # noqa: BLE001

        return set()


# --------------------------------------------------------------------------- #
# Voces disponibles (macOS say)
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class VoiceInfo:
    """Una voz instalada en macOS."""

    base: str          # nombre base, p. ej. "Reed"

    full: str          # nombre para `say -v`, p. ej. "Reed (Español (México))"

    locale: str        # p. ej. "es_MX"


def list_voices() -> list[VoiceInfo]:
    """Lista las voces instaladas en macOS (comando say)."""

    try:

        out = subprocess.run(
            ["say", "-v", "?"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    except (subprocess.CalledProcessError, FileNotFoundError):

        return []

    voices: list[VoiceInfo] = []

    for line in out.splitlines():

        # Tras '#' viene el sample; antes está "<nombre...> <locale>".
        head = line.split("#", 1)[0].rstrip()

        # El locale va al final: es_MX, en_US, en, zh_CN, etc.
        m = re.search(r"\s([a-z]{2}(?:[_-][A-Za-z]{2,3})?)$", head)

        if not m:

            continue

        locale = m.group(1).replace("-", "_")

        full = head[: m.start()].rstrip()

        # El nombre base quita el sufijo "(Idioma (Región))".
        base = re.sub(r"\s*\(.*\)\s*$", "", full).strip()

        if base:

            voices.append(VoiceInfo(base=base, full=full, locale=locale))

    return voices


def available_voices() -> set[str]:
    """Nombres base de las voces instaladas."""

    return {v.base for v in list_voices()}


def resolve_voice(requested: str, language: str = "es-MX") -> str | None:
    """Resuelve una voz a su variante del idioma indicado.

    Las voces multilingües (Reed, Eddy, Rocko…) requieren el nombre
    completo con idioma para no leerse en inglés. Devuelve el nombre
    que debe pasarse a `say`, o None si no se encuentra la voz.
    """

    req_base = re.sub(r"\s*\(.*\)\s*$", "", requested).strip().lower()

    target = language.replace("-", "_").lower()

    target_lang = target.split("_")[0]

    voices = list_voices()

    matches = [v for v in voices if v.base.lower() == req_base]

    if not matches:

        return None

    # 1) Coincidencia exacta de locale (es_MX)
    for v in matches:

        if v.locale.lower() == target:

            return v.full

    # 2) Mismo idioma, cualquier región (es_*)
    for v in matches:

        if v.locale.lower().startswith(target_lang):

            return v.full

    # 3) Cualquier variante instalada de esa voz
    return matches[0].full


# --------------------------------------------------------------------------- #
# Síntesis de audio
# --------------------------------------------------------------------------- #

def _ffmpeg(args: list[str]) -> None:

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
        check=True,
        capture_output=True,
    )


def _synth_say(text: str, voice: str, dest: Path, tmp: Path, i: int, rate: int | None) -> Path:
    """Sintetiza un turno con el comando `say` de macOS. Devuelve un .aiff."""

    text_file = tmp / f"turn_{i}.txt"

    text_file.write_text(text, encoding="utf8")

    say_cmd = ["say", "-v", voice, "-f", str(text_file), "-o", str(dest)]

    if rate:

        say_cmd += ["-r", str(rate)]

    subprocess.run(say_cmd, check=True, capture_output=True)

    return dest


def _synth_edge(text: str, voice: str, dest: Path, rate: int | None) -> Path:
    """Sintetiza un turno con edge-tts (voces neuronales). Devuelve un .mp3."""

    import asyncio

    import edge_tts

    kwargs: dict = {}

    if rate:

        # `say` usa palabras/min (~175 base); edge usa porcentaje.
        pct = round((rate / 175.0 - 1.0) * 100)

        kwargs["rate"] = f"{'+' if pct >= 0 else ''}{pct}%"

    async def _run() -> None:

        communicate = edge_tts.Communicate(text, voice, **kwargs)

        await communicate.save(str(dest))

    asyncio.run(_run())

    return dest


def synthesize(
    script: PodcastScript,
    out_dir: Path,
    fmt: str = "m4a",
    rate: int | None = None,
) -> Path:
    """Sintetiza el guion a un único archivo de audio y devuelve su ruta."""

    fmt = fmt.lower().lstrip(".")

    if fmt not in AUDIO_CODECS:

        raise ValueError(f"Formato de audio no soportado: {fmt}")

    out_dir.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="stt_pod_"))

    try:

        silence = tmp / "silence.wav"

        _ffmpeg([
            "-f", "lavfi",
            "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
            "-t", f"{script.pause:.3f}",
            str(silence),
        ])

        wavs: list[Path] = []

        for i, turn in enumerate(script.turns):

            if script.engine == "edge":

                src = _synth_edge(turn.text, turn.voice, tmp / f"turn_{i}.mp3", rate)

            else:

                src = _synth_say(turn.text, turn.voice, tmp / f"turn_{i}.aiff", tmp, i, rate)

            wav = tmp / f"turn_{i}.wav"

            _ffmpeg(["-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1", str(wav)])

            wavs.append(wav)

        if not wavs:

            raise ValueError("El guion no contiene turnos de habla válidos.")

        list_file = tmp / "concat.txt"

        lines: list[str] = []

        for i, wav in enumerate(wavs):

            lines.append(f"file '{wav}'")

            if i < len(wavs) - 1:

                lines.append(f"file '{silence}'")

        list_file.write_text("\n".join(lines), encoding="utf8")

        out_path = out_dir / f"{safe_filename(script.title)}.{fmt}"

        _ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            *AUDIO_CODECS[fmt],
            str(out_path),
        ])

        return out_path

    finally:

        shutil.rmtree(tmp, ignore_errors=True)
