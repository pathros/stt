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
            )

    try:

        pages = os.sysconf("SC_PHYS_PAGES")

        page = os.sysconf("SC_PAGE_SIZE")

        total = pages * page / (1024 ** 3)

    except (AttributeError, OSError, ValueError):

        total = 0.0

    return float(total), float(total)


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
