from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json


CONFIG_PATH = (
    Path(__file__).resolve()
    .parents[2]
    / "config"
    / "config.json"
)


@dataclass(slots=True)
class Config:

    model: str

    language: str

    output: Path

    formats: list[str]

    beam_size: int

    vad_filter: bool

    compute_type: str

    # Vacío = prompt automático en español; otro texto lo sobrescribe.
    initial_prompt: str = ""


def load_config() -> Config:

    with open(CONFIG_PATH, encoding="utf8") as f:

        try:

            data = json.load(f)

        except json.JSONDecodeError as exc:

            raise SystemExit(
                f"config.json inválido ({CONFIG_PATH}): {exc}\n"
                "En Windows, en \"output\" usa barras / "
                '(ej. "C:/Users/.../Transcripciones") '
                "o dobles \\\\ ; una sola \\ rompe el JSON."
            ) from exc

    data.setdefault("initial_prompt", "")

    data["output"] = Path(data["output"]).expanduser()

    return Config(**data)


def save_config(config: Config):

    data = asdict(config)

    data["output"] = str(data["output"])

    with open(CONFIG_PATH, "w", encoding="utf8") as f:

        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False,
        )
