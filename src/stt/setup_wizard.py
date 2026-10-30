from __future__ import annotations

import os
from pathlib import Path

from stt.config import CONFIG_PATH, Config, save_config
from stt.hardware import diagnose, diarization_verdict, format_diarization_verdict


def _windows_folder(csidl: int, fallback: Path) -> Path:

    if os.name != "nt":

        return fallback

    import ctypes

    buffer = ctypes.create_unicode_buffer(260)

    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) != 0:

        return fallback

    return Path(buffer.value)


def downloads_dir() -> Path:
    """Carpeta Descargas. En Windows usa la carpeta conocida del sistema."""

    if os.name != "nt":

        return Path.home() / "Downloads"

    import ctypes

    class GUID(ctypes.Structure):

        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    folder_id = GUID(
        0x374DE290,
        0x123F,
        0x4565,
        (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B),
    )

    pointer = ctypes.c_wchar_p()

    shell32 = ctypes.windll.shell32

    ole32 = ctypes.windll.ole32

    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]

    shell32.SHGetKnownFolderPath.restype = ctypes.c_long

    if shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(pointer)) != 0:

        return Path.home() / "Downloads"

    try:

        return Path(pointer.value)

    finally:

        ole32.CoTaskMemFree(pointer)


def desktop_dir() -> Path:

    found = _windows_folder(0x0010, Path.home() / "Desktop")

    if found.exists():

        return found

    localized = Path.home() / "Escritorio"

    if localized.exists():

        return localized

    return found


def project_dir() -> Path:

    return CONFIG_PATH.parents[1]


def _ask(label: str, default: str) -> str:

    typed = input(f"{label}\n[{default}]: ").strip().strip('"')

    return typed or default


def _write_bat(path: Path, lines: list[str]) -> None:

    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def write_shortcuts(project: Path, desktop: Path) -> tuple[Path, Path]:
    """Crea en el Escritorio el acceso de arrastrar y el de volver a configurar."""

    desktop.mkdir(parents=True, exist_ok=True)

    home = str(project)

    transcribir = desktop / "Transcribir.bat"

    configurar = desktop / "Configurar-transcripcion.bat"

    _write_bat(
        transcribir,
        [
            "@echo off",
            "setlocal",
            "set \"HF_HUB_DISABLE_SYMLINKS_WARNING=1\"",
            f"set \"STT_HOME={home}\"",
            "set \"STT_EXE=%STT_HOME%\\.venv\\Scripts\\stt.exe\"",
            "cd /d \"%STT_HOME%\" 2>nul",
            "if not exist \"%STT_EXE%\" (",
            "  echo No se encuentra el programa. Vuelva a ejecutar Instalar.bat",
            "  pause",
            "  exit /b 1",
            ")",
            "if \"%~1\"==\"\" (",
            "  echo.",
            "  echo  Arrastre el archivo de audio encima de este icono.",
            "  echo  Por ejemplo un .mp3 de una entrevista.",
            "  echo.",
            "  pause",
            "  exit /b 1",
            ")",
            "\"%STT_EXE%\" \"%~1\"",
            "echo.",
            "pause",
        ],
    )

    _write_bat(
        configurar,
        [
            "@echo off",
            "setlocal",
            "chcp 65001 >nul",
            f"set \"STT_HOME={home}\"",
            "set \"STT_EXE=%STT_HOME%\\.venv\\Scripts\\stt.exe\"",
            "cd /d \"%STT_HOME%\"",
            "\"%STT_EXE%\" configurar",
            "pause",
        ],
    )

    return transcribir, configurar


def run_setup(auto: bool = False) -> None:
    """Diagnóstico, carpeta, formato Word y acceso directo. Idioma: automático.

    Con ``auto=True`` no pregunta nada: Word, carpeta Descargas y el
    modelo que quepa en la memoria. Sirve para quien no quiere tocar rutas.
    """

    report = diagnose()

    default_out = downloads_dir()

    print()
    print("Configuración de la transcripción")
    print("=================================")
    print()
    print(f"Procesador: {report.cpu} ({report.cores} núcleos)")
    print(f"Memoria: {report.ram_gb:.1f} GB (libres ahora {report.ram_free_gb:.1f} GB)")
    print(f"Espacio libre en disco: {report.disk_free_gb:.1f} GB")
    print(
        "Programa de audio (ffmpeg): "
        + ("listo" if report.ffmpeg else "NO está instalado")
    )
    print()
    print(report.note)
    print(f"Modelo que se usará: {report.model}")
    print()
    print(format_diarization_verdict(diarization_verdict()))

    if not report.ffmpeg:

        print("Sin ffmpeg algunos audios no se abren.")
        print("Cierre esta ventana, ábrala otra vez, o en PowerShell ejecute:")
        print("  winget install Gyan.FFmpeg")
        print()

    if auto:

        model = report.model

        output = default_out

        formats = ["docx"]

        print("No hay que escribir rutas ni abrir archivos de configuración.")
        print("Aunque el nombre de usuario tenga espacios, se usa solo.")
        print(f"Carpeta: {output}")
        print("Formato: Word (.docx)")
        print("Idioma: se detecta solo a partir del audio.")

    else:

        model = _ask(
            "Enter para aceptar el modelo, o escriba small o medium",
            report.model,
        ).lower()

        if model not in {"tiny", "base", "small", "medium", "large-v3", "large-v2"}:

            print(f"No reconozco «{model}». Se deja {report.model}.")

            model = report.model

        print()
        print("Enter usa la carpeta Descargas. No hace falta editar config.json.")

        output = Path(_ask("Carpeta de salida", str(default_out))).expanduser()

        print()
        print("Formato del archivo resultante:")
        print("  1  Word (.docx) — recomendado, para revisar y ajustar párrafos")
        print("  2  Texto (.txt)")
        print("  3  Word y texto")

        choice = _ask("Elija 1, 2 o 3", "1")

        formats = {
            "1": ["docx"],
            "2": ["txt"],
            "3": ["docx", "txt"],
            "docx": ["docx"],
            "txt": ["txt"],
        }.get(choice, ["docx"])

    output.mkdir(parents=True, exist_ok=True)

    cfg = Config(
        model=model,
        language="auto",
        output=output,
        formats=formats,
        beam_size=report.beam_size,
        vad_filter=True,
        compute_type="int8",
        initial_prompt="",
        batch_size=report.batch_size,
    )

    save_config(cfg)

    print()
    print("El modelo se descarga de la cuenta oficial Systran, si aún no está.")
    print("Después se comprueba archivo por archivo. Si no coincide, no se usa.")

    from stt.model_audit import ensure_official_model

    ensure_official_model(model)

    print()
    print("El idioma no se fija: se detecta solo a partir del audio.")
    print("El texto sale en párrafos (separados cuando hay una pausa).")
    print(f"Se guardará en: {output}")
    print(f"Formato: {', '.join(formats)}")

    if os.name == "nt":

        transcribir, configurar = write_shortcuts(project_dir(), desktop_dir())

        print()
        print("En el Escritorio quedaron dos iconos:")
        print(f"  {transcribir.name}")
        print("    Arrastre ahí el audio de la entrevista.")
        print(f"  {configurar.name}")
        print("    Para cambiar carpeta, formato o modelo más adelante.")

    else:

        print()
        print("En esta computadora no se crea acceso de Escritorio de Windows.")
        print("Para transcribir: stt ruta/al/audio.mp3")

    print()
    print("Listo.")
    print()
