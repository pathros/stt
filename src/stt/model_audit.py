"""Comprueba que el modelo de faster-whisper sea el de Systran.

Solo se aceptan revisiones ya revisadas. El peso tiene que coincidir
byte por byte con el publicado y estar en el formato binario de
CTranslate2 (WhisperSpec), no en pickle ni en zip. El config no puede
pedir código externo.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path


class ModelAuditError(RuntimeError):
    """El modelo no es el oficial o no se pudo comprobar."""


@dataclass(frozen=True, slots=True)
class OfficialFile:

    sha256: str

    size: int


@dataclass(frozen=True, slots=True)
class OfficialModel:

    name: str

    repo: str

    revision: str

    files: dict[str, OfficialFile]


def _file(sha256: str, size: int) -> OfficialFile:

    return OfficialFile(sha256=sha256, size=size)


# Tokenizer y vocabulario compartidos por los modelos anteriores a large-v3.
_TOKENIZER = _file(
    "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
    2_203_239,
)
_VOCABULARY = _file(
    "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
    459_861,
)

# Revisiones inmutables de huggingface.co/Systran. No se sigue la rama main:
# si el publicador cambia los archivos, esta versión sigue exigiendo estas huellas.
_OFFICIAL: dict[str, OfficialModel] = {
    "tiny": OfficialModel(
        name="tiny",
        repo="Systran/faster-whisper-tiny",
        revision="d90ca5fe260221311c53c58e660288d3deb8d356",
        files={
            "config.json": _file(
                "a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8",
                2_249,
            ),
            "model.bin": _file(
                "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
                75_538_270,
            ),
            "tokenizer.json": _TOKENIZER,
            "vocabulary.txt": _VOCABULARY,
        },
    ),
    "base": OfficialModel(
        name="base",
        repo="Systran/faster-whisper-base",
        revision="ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        files={
            "config.json": _file(
                "56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a",
                2_309,
            ),
            "model.bin": _file(
                "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
                145_217_532,
            ),
            "tokenizer.json": _TOKENIZER,
            "vocabulary.txt": _VOCABULARY,
        },
    ),
    "small": OfficialModel(
        name="small",
        repo="Systran/faster-whisper-small",
        revision="536b0662742c02347bc0e980a01041f333bce120",
        files={
            "config.json": _file(
                "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
                2_370,
            ),
            "model.bin": _file(
                "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
                483_546_902,
            ),
            "tokenizer.json": _TOKENIZER,
            "vocabulary.txt": _VOCABULARY,
        },
    ),
    "medium": OfficialModel(
        name="medium",
        repo="Systran/faster-whisper-medium",
        revision="08e178d48790749d25932bbc082711ddcfdfbc4f",
        files={
            "config.json": _file(
                "3622a2ddc41ec0e0fd4e68c13c6830f03b90c38d89aaad184de02c8c642cf807",
                2_257,
            ),
            "model.bin": _file(
                "9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae",
                1_527_906_378,
            ),
            "tokenizer.json": _TOKENIZER,
            "vocabulary.txt": _VOCABULARY,
        },
    ),
    "large-v2": OfficialModel(
        name="large-v2",
        repo="Systran/faster-whisper-large-v2",
        revision="f0fe81560cb8b68660e564f55dd99207059c092e",
        files={
            "config.json": _file(
                "d86b7a7664a12559d644aa210a32ce9a7e03913e794b7ea4fb7182de69e273a7",
                2_796,
            ),
            "model.bin": _file(
                "bf2a9746382e1aa7ffff6b3a0d137ed9edbd9670c3b87e5d35f5e85e70d0333a",
                3_086_912_962,
            ),
            "tokenizer.json": _TOKENIZER,
            "vocabulary.txt": _VOCABULARY,
        },
    ),
    "large-v3": OfficialModel(
        name="large-v3",
        repo="Systran/faster-whisper-large-v3",
        revision="edaa852ec7e145841d8ffdb056a99866b5f0a478",
        files={
            "config.json": _file(
                "a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9",
                2_394,
            ),
            "model.bin": _file(
                "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1",
                3_087_284_237,
            ),
            "preprocessor_config.json": _file(
                "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
                340,
            ),
            "tokenizer.json": _file(
                "6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca",
                2_480_617,
            ),
            "vocabulary.json": _file(
                "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
                1_068_114,
            ),
        },
    ),
}

_DANGEROUS_SUFFIXES = {
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".py",
    ".pyc",
    ".exe",
    ".dll",
    ".so",
    ".bat",
    ".ps1",
    ".sh",
    ".zip",
}

_BANNED_CONFIG_KEYS = {
    "auto_map",
    "trust_remote_code",
    "custom_code",
    "auto_class",
}

_CONFIG_TEXT_NEEDLES = (
    "pickle",
    "eval(",
    "exec(",
    "__import__",
    "os.system",
    "__reduce__",
)


def known_models() -> tuple[str, ...]:

    return tuple(_OFFICIAL)


def official_model(name: str) -> OfficialModel:

    key = (name or "").strip().lower()

    spec = _OFFICIAL.get(key)

    if spec is None:

        known = ", ".join(known_models())

        raise ModelAuditError(
            f"No hay un modelo auditado llamado «{name}». "
            f"Use uno de: {known}."
        )

    return spec


def _sha256(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as handle:

        for chunk in iter(lambda: handle.read(1024 * 1024), b""):

            digest.update(chunk)

    return digest.hexdigest()


def _read_header(path: Path, size: int = 64) -> bytes:

    with path.open("rb") as handle:

        return handle.read(size)


def _assert_whisper_weights(path: Path) -> None:

    header = _read_header(path, 64)

    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06"):

        raise ModelAuditError(
            "model.bin es un ZIP. Ese formato puede traer código y no se abre."
        )

    if header.startswith(b"\x80"):

        raise ModelAuditError(
            "model.bin es un pickle. Ese formato puede ejecutar código al abrirse."
        )

    if len(header) < 8:

        raise ModelAuditError("model.bin está incompleto.")

    name_len = int.from_bytes(header[4:6], "little")

    if not 1 <= name_len <= 32:

        raise ModelAuditError(
            "model.bin no tiene el formato binario de CTranslate2."
        )

    spec_name = header[6 : 6 + name_len]

    if len(spec_name) < name_len:

        with path.open("rb") as handle:

            handle.seek(6)

            spec_name = handle.read(name_len)

    if not spec_name.startswith(b"WhisperSpec"):

        raise ModelAuditError(
            "model.bin no es un modelo Whisper de CTranslate2 "
            "(no dice WhisperSpec)."
        )


def _assert_config_has_no_code(path: Path) -> None:

    raw = path.read_bytes()

    if raw.startswith(b"PK") or raw.startswith(b"\x80"):

        raise ModelAuditError(f"{path.name} no es un JSON de configuración.")

    try:

        data = json.loads(raw.decode("utf-8"))

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:

        raise ModelAuditError(f"{path.name} no es JSON válido.") from exc

    if not isinstance(data, dict):

        raise ModelAuditError(f"{path.name} no es un objeto JSON.")

    banned = sorted(set(data) & _BANNED_CONFIG_KEYS)

    if banned:

        raise ModelAuditError(
            f"{path.name} pide código externo ({', '.join(banned)})."
        )

    lowered = raw.decode("utf-8").lower()

    for needle in _CONFIG_TEXT_NEEDLES:

        if needle in lowered:

            raise ModelAuditError(
                f"{path.name} incluye «{needle}», que no corresponde "
                "a un modelo de solo transcripción."
            )


def _assert_not_executable_blob(path: Path) -> None:

    header = _read_header(path, 8)

    if header.startswith(b"PK") or header.startswith(b"\x80"):

        raise ModelAuditError(
            f"{path.name} parece un zip o un pickle. No se acepta."
        )


def _assert_no_extra_files(directory: Path, allowed: set[str]) -> None:

    for path in directory.rglob("*"):

        if not path.is_file():

            continue

        relative = path.relative_to(directory)

        if path.suffix.lower() in _DANGEROUS_SUFFIXES:

            raise ModelAuditError(
                f"Hay un archivo que no pertenece al modelo oficial: {relative}."
            )

        if any(part.startswith(".") for part in relative.parts):

            continue

        if path.name not in allowed or len(relative.parts) != 1:

            raise ModelAuditError(
                f"Hay un archivo inesperado en el modelo: {relative}."
            )


def audit_model_directory(directory: Path, name: str) -> OfficialModel:
    """Recalcula las huellas y rechaza el directorio si no es el oficial."""

    spec = official_model(name)

    directory = directory.expanduser()

    if not directory.is_dir():

        raise ModelAuditError(f"No existe la carpeta del modelo: {directory}")

    _assert_no_extra_files(directory, set(spec.files))

    for filename, expected in spec.files.items():

        path = directory / filename

        if not path.is_file():

            raise ModelAuditError(f"Falta {filename} en {directory}.")

        size = path.stat().st_size

        if size != expected.size:

            raise ModelAuditError(
                f"{filename} no tiene el tamaño del archivo oficial "
                f"({size} bytes; el de Systran mide {expected.size})."
            )

        digest = _sha256(path)

        if digest != expected.sha256:

            raise ModelAuditError(
                f"{filename} no coincide con {spec.repo} "
                f"(revisión {spec.revision[:12]}). "
                "No se usa: puede estar alterado."
            )

    _assert_whisper_weights(directory / "model.bin")

    _assert_config_has_no_code(directory / "config.json")

    preprocessor = directory / "preprocessor_config.json"

    if preprocessor.is_file():

        _assert_config_has_no_code(preprocessor)

    for filename in spec.files:

        if filename == "model.bin":

            continue

        _assert_not_executable_blob(directory / filename)

    return spec


def _project_models_dir() -> Path:

    from stt.config import CONFIG_PATH

    return CONFIG_PATH.parents[1] / "models"


def _download(spec: OfficialModel, dest: Path, attempts: int = 3) -> None:

    import os

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    from huggingface_hub import snapshot_download

    dest.mkdir(parents=True, exist_ok=True)

    last: Exception | None = None

    for attempt in range(1, attempts + 1):

        try:

            snapshot_download(
                spec.repo,
                revision=spec.revision,
                local_dir=str(dest),
                allow_patterns=list(spec.files),
            )

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

    raise ModelAuditError(
        "No se pudo descargar el modelo oficial de Systran.\n"
        "Revise la conexión y vuelva a ejecutar la instalación.\n"
        f"Detalle: {last}"
    )


def ensure_official_model(name: str, search: list[Path] | None = None) -> Path:
    """Devuelve la carpeta auditada. Si no está, la baja de la revisión fijada.

    Una copia local que no coincida se rechaza. No se sustituye en silencio
    por otra carpeta: así un archivo alterado no se llega a cargar.
    """

    try:

        return _ensure_official_model(name, search)

    except ModelAuditError as exc:

        raise SystemExit(
            "No se instaló el modelo de transcripción.\n"
            f"{exc}\n"
            "Solo se aceptan los archivos oficiales de Systran, "
            "sin pickle ni código.\n"
            "Si esa carpeta ya estaba en el disco, bórrela y vuelva "
            "a ejecutar la instalación para bajar la copia oficial."
        ) from exc


def _ensure_official_model(name: str, search: list[Path] | None) -> Path:

    spec = official_model(name)

    candidates: list[Path] = []

    for path in search or []:

        expanded = path.expanduser()

        if expanded not in candidates:

            candidates.append(expanded)

    default = _project_models_dir() / spec.name

    if default not in candidates:

        candidates.append(default)

    for path in candidates:

        if (path / "model.bin").is_file():

            print(f"Comprobando que el modelo es el oficial de Systran: {path}")
            print("Se lee el archivo completo. Puede tardar un momento.")

            audit_model_directory(path, spec.name)

            print(
                "El modelo coincide con el publicado por Systran. "
                "Es CTranslate2: no puede ejecutar código al abrirse."
            )

            return path

    dest = default

    print(
        "Descargando el modelo oficial de Systran "
        f"({spec.repo}, revisión {spec.revision[:12]})."
    )
    print("Al terminar se comprueba la huella de cada archivo.")

    _download(spec, dest)

    try:

        print("Comprobando la descarga contra las huellas oficiales…")

        audit_model_directory(dest, spec.name)

    except ModelAuditError:

        shutil.rmtree(dest, ignore_errors=True)

        raise

    print(
        "El modelo descargado es el oficial de Systran "
        "y no trae código ejecutable."
    )

    return dest
