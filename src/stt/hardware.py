from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class HardwareReport:

    cpu: str

    cores: int

    ram_gb: float

    ram_free_gb: float

    disk_free_gb: float

    ffmpeg: bool

    model: str

    beam_size: int

    batch_size: int

    note: str


def recommend(ram_gb: float, disk_free_gb: float) -> tuple[str, int, int, str]:
    """Elige modelo y velocidad según la memoria, sin bajar de calidad de más."""

    if ram_gb and ram_gb < 8:

        model, beam, batch = "small", 1, 4

        note = (
            "Hay poca memoria. Se usará un modelo ligero "
            "para que la computadora no se trabe."
        )

    elif ram_gb and ram_gb < 12:

        model, beam, batch = "small", 2, 4

        note = (
            "La memoria es justa. Se usará un modelo ligero, "
            "más rápido, con buena calidad para entrevistas."
        )

    else:

        model, beam, batch = "medium", 2, 8

        note = (
            "Hay memoria suficiente. Se usará el modelo medio: "
            "buen equilibrio entre calidad del texto y tiempo de espera."
        )

    if disk_free_gb and disk_free_gb < 8:

        note += " Queda poco espacio en disco; conviene liberar al menos 8 GB."

    return model, beam, batch, note


def cpu_name() -> str:

    if os.name == "nt":

        try:

            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:

                name, _ = winreg.QueryValueEx(key, "ProcessorNameString")

            return str(name).strip()

        except OSError:

            pass

    return (platform.processor() or platform.machine() or "desconocido").strip()


def memory_gb() -> tuple[float, float]:
    """Devuelve (RAM total, RAM libre) en GB."""

    total, free, _known = memory_status()

    return total, free


def memory_status() -> tuple[float, float, bool]:
    """Devuelve (RAM total, RAM libre, si la libre se midió de verdad)."""

    if os.name == "nt":

        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):

            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()

        status.dwLength = ctypes.sizeof(status)

        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):

            return (
                status.ullTotalPhys / (1024 ** 3),
                status.ullAvailPhys / (1024 ** 3),
                True,
            )

    try:

        pages = os.sysconf("SC_PHYS_PAGES")

        page = os.sysconf("SC_PAGE_SIZE")

        total = float(pages * page / (1024 ** 3))

    except (AttributeError, OSError, ValueError):

        total = 0.0

    if platform.system() == "Darwin":

        free = _darwin_available_gb()

        if free is not None:

            return total, free, True

    elif os.name == "posix":

        free = _linux_available_gb()

        if free is not None:

            return total, free, True

    return total, total, False


def _darwin_available_gb() -> float | None:
    """Memoria que macOS puede usar ya (libre + inactiva + especulativa)."""

    import subprocess

    try:

        out = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)

    except (OSError, subprocess.CalledProcessError):

        return None

    page_size = 4096

    counts: dict[str, int] = {}

    for line in out.splitlines():

        if "page size of" in line:

            raw = line.split("page size of", 1)[1].split()[0]

            if raw.isdigit():

                page_size = int(raw)

        if ":" not in line:

            continue

        key, val = line.split(":", 1)

        number = val.strip().strip(".").replace(".", "")

        if number.isdigit():

            counts[key.strip()] = int(number)

    pages = (
        counts.get("Pages free", 0)
        + counts.get("Pages inactive", 0)
        + counts.get("Pages speculative", 0)
    )

    if pages <= 0:

        return None

    return pages * page_size / (1024 ** 3)


def _linux_available_gb() -> float | None:

    try:

        text = Path("/proc/meminfo").read_text(encoding="utf8")

    except OSError:

        return None

    for line in text.splitlines():

        if line.startswith("MemAvailable:"):

            parts = line.split()

            if len(parts) >= 2 and parts[1].isdigit():

                return int(parts[1]) / (1024 ** 2)

    return None


def diagnose() -> HardwareReport:

    ram, free = memory_gb()

    disk = shutil.disk_usage(Path.home()).free / (1024 ** 3)

    model, beam, batch, note = recommend(ram, disk)

    return HardwareReport(
        cpu=cpu_name(),
        cores=os.cpu_count() or 1,
        ram_gb=ram,
        ram_free_gb=free,
        disk_free_gb=disk,
        ffmpeg=shutil.which("ffmpeg") is not None,
        model=model,
        beam_size=beam,
        batch_size=batch,
        note=note,
    )


# Separar voces corre después de transcribir, no a la vez.
# 12 GB: sistema + el modelo de texto, y luego el de voces, sin quedarse en cero.
# 5 GB: PyTorch de CPU y pyannote. 1 GB: los pesos del modelo de voces.
MIN_RAM_GB = 12.0

MIN_FREE_RAM_GB = 4.0

PACKAGE_DISK_GB = 5.0

MODEL_DISK_GB = 1.0

DIARIZE_MODEL_ID = "pyannote/speaker-diarization-community-1"


@dataclass(slots=True)
class DiarizationVerdict:
    """Dictamen de si este equipo puede instalar y usar la separación de voces."""

    possible: bool

    installed: bool

    ram_gb: float

    ram_free_gb: float

    disk_free_gb: float

    ffmpeg: bool

    lines: list[str]

    dictamen: str


def voices_cli(args: str) -> str:
    """Cómo invocar stt en este sistema, desde la carpeta del programa."""

    if os.name == "nt":

        return r".venv\Scripts\stt.exe " + args

    return "stt " + args


def install_root() -> Path:

    from stt.config import CONFIG_PATH

    return CONFIG_PATH.parents[1]


def voices_package_installed() -> bool:
    """True si pyannote ya está en este Python. No lo importa (no carga PyTorch)."""

    import importlib.util

    try:

        return importlib.util.find_spec("pyannote.audio") is not None

    except (ImportError, ValueError, ModuleNotFoundError):

        return False


def local_pipeline_dir() -> Path | None:
    """Carpeta ya descargada del modelo de voces, si trae config.yaml."""

    candidates: list[Path] = []

    env = os.environ.get("STT_DIARIZE_PATH", "").strip()

    if env:

        candidates.append(Path(env).expanduser())

    root = install_root() / "models"

    candidates.append(root / "speaker-diarization-community-1")

    candidates.append(root / "pyannote-speaker-diarization-community-1")

    for path in candidates:

        if (path / "config.yaml").is_file():

            return path

    return None


def huggingface_token() -> str:
    """Token de solo lectura, si ya está en el entorno o en config/hf_token."""

    for key in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"):

        value = os.environ.get(key, "").strip()

        if value:

            return value

    path = install_root() / "config" / "hf_token"

    if path.is_file():

        return path.read_text(encoding="utf8").strip()

    return ""


def model_cache_dir() -> Path:
    """Dónde cae la descarga del modelo. Por defecto, dentro del programa."""

    env = os.environ.get("HF_HOME", "").strip()

    if env:

        return Path(env).expanduser()

    return install_root() / ".cache" / "huggingface"


def _free_gb(path: Path) -> float:

    probe = path.expanduser()

    if not probe.exists():

        probe = probe.parent

    if not probe.exists():

        probe = Path.home()

    return shutil.disk_usage(probe).free / (1024 ** 3)


def _same_drive(left: Path, right: Path) -> bool:

    return left.expanduser().resolve().anchor == right.expanduser().resolve().anchor


def diarization_verdict() -> DiarizationVerdict:
    """Revisa memoria, disco y ffmpeg. No instala nada."""

    ram, free, free_known = memory_status()

    installed = voices_package_installed()

    local = local_pipeline_dir()

    token = huggingface_token()

    ffmpeg = shutil.which("ffmpeg") is not None

    package_gb = 0.0 if installed else PACKAGE_DISK_GB

    model_gb = 0.0 if local is not None else MODEL_DISK_GB

    program_disk = install_root()

    cache_disk = model_cache_dir()

    program_free = _free_gb(program_disk)

    cache_free = program_free if _same_drive(program_disk, cache_disk) else _free_gb(cache_disk)

    if _same_drive(program_disk, cache_disk):

        disk_free = program_free

        disk_need = package_gb + model_gb

        disk_ok = disk_free >= disk_need

        if disk_need:

            disk_line = (
                f"Espacio libre en disco: {disk_free:.1f} GB "
                f"(hacen falta unos {disk_need:.0f} GB)."
            )

        else:

            disk_line = (
                f"Espacio libre en disco: {disk_free:.1f} GB "
                "(el extra ya no pide más espacio)."
            )

    else:

        disk_free = min(program_free, cache_free)

        disk_ok = program_free >= package_gb and cache_free >= model_gb

        disk_need = package_gb + model_gb

        disk_line = (
            f"Espacio libre: {program_free:.1f} GB en el disco del programa "
            f"(hacen falta {package_gb:.0f} GB) y {cache_free:.1f} GB "
            f"donde se guarda el modelo (hacen falta {model_gb:.0f} GB)."
        )

    ram_known = ram > 0

    ram_ok = ram_known and ram >= MIN_RAM_GB

    reasons: list[str] = []

    lines = [
        "No viene con la transcripción. En una entrevista o un podcast marca "
        "quién habla (Hablante 1, Hablante 2). No adivina el nombre real.",
        "",
        (
            f"Memoria de la computadora: {ram:.1f} GB "
            f"(hacen falta al menos {MIN_RAM_GB:.0f} GB)."
            if ram_known
            else "Memoria de la computadora: no se pudo medir."
        ),
    ]

    if not ram_known:

        lines.append("  Sin esa cifra no se instala el extra.")

        reasons.append("no se pudo medir la memoria")

    elif ram_ok:

        lines.append(
            "  Alcanza para transcribir y, después, separar voces "
            "(una cosa y luego la otra, no las dos a la vez)."
        )

    else:

        lines.append(
            "  No alcanza. Con menos de 12 GB el equipo se queda corto "
            "aunque se haga por partes."
        )

        reasons.append(f"solo hay {ram:.0f} GB de memoria y hacen falta 12 GB")

    if free_known:

        lines.append(f"Memoria libre ahora: {free:.1f} GB.")

        if free < MIN_FREE_RAM_GB:

            lines.append(
                "  Antes de usarla, cierre otros programas "
                f"(conviene dejar al menos {MIN_FREE_RAM_GB:.0f} GB libres)."
            )

        else:

            lines.append("  Hay memoria libre suficiente para usarla ahora.")

    lines.append(disk_line)

    if disk_ok:

        if disk_need == 0:

            lines.append("  El extra y el modelo ya están en disco.")

        else:

            lines.append("  El disco alcanza.")

    else:

        lines.append("  No alcanza. Libere espacio y vuelva a revisar.")

        reasons.append(
            f"quedan {disk_free:.1f} GB libres y hacen falta unos {disk_need:.0f} GB"
        )

    if ffmpeg:

        lines.append("ffmpeg (abre los audios): listo.")

    else:

        lines.append("ffmpeg (abre los audios): no está instalado.")

        reasons.append("falta ffmpeg")

    if installed:

        lines.append("Extra de voces: ya está instalado.")

    else:

        lines.append("Extra de voces: no está instalado.")

    if local is not None:

        lines.append(f"Modelo de voces: ya está en {local}.")

    elif token:

        lines.append(
            "Modelo de voces: todavía no está en disco. "
            "Hay un token de Hugging Face; se baja la primera vez."
        )

    else:

        lines.append(
            "Modelo de voces: la primera descarga pide una cuenta gratuita "
            "de Hugging Face y aceptar las condiciones del modelo. "
            "Después funciona sin internet."
        )

    possible = not reasons

    if possible and installed:

        dictamen = (
            "Dictamen: este equipo sí puede separar voces y el extra ya está instalado. "
            "La transcripción normal no lo usa. "
            "Para una entrevista, desde la carpeta del programa: "
            + voices_cli("entrevista.m4a --speakers 2")
        )

    elif possible:

        dictamen = (
            "Dictamen: sí se puede instalar en este equipo. "
            "No se instala solo, porque ocupa varios gigas. "
            "Para instalarlo, desde la carpeta del programa: "
            + voices_cli("voces")
        )

    else:

        dictamen = (
            "Dictamen: no se instala en este equipo ("
            + "; ".join(reasons)
            + "). La transcripción de siempre sigue igual, sin separar voces."
        )

    return DiarizationVerdict(
        possible=possible,
        installed=installed,
        ram_gb=ram,
        ram_free_gb=free,
        disk_free_gb=disk_free,
        ffmpeg=ffmpeg,
        lines=lines,
        dictamen=dictamen,
    )


def format_diarization_verdict(verdict: DiarizationVerdict) -> str:

    body = "\n".join(verdict.lines)

    return (
        "Separar voces (opcional)\n"
        "------------------------\n"
        f"{body}\n\n"
        f"{verdict.dictamen}\n"
    )
