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


def load_config() -> Config:

    with open(CONFIG_PATH, encoding="utf8") as f:

        data = json.load(f)

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
