"""Genera INSTALACION-WINDOWS.docx para usuarios que no usan la terminal."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "INSTALACION-WINDOWS.docx"
ZIP_URL = "https://github.com/pathros/stt/archive/refs/heads/main.zip"


def add_heading(doc: Document, text: str, level: int = 1) -> None:

    heading = doc.add_heading(text, level=level)

    for run in heading.runs:

        run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)


def add_body(doc: Document, text: str, bold: bool = False) -> None:

    paragraph = doc.add_paragraph()

    run = paragraph.add_run(text)

    run.bold = bold

    run.font.size = Pt(12)

    run.font.name = "Calibri"

    paragraph.paragraph_format.space_after = Pt(8)


def add_step(doc: Document, number: str, title: str, lines: list[str]) -> None:

    add_heading(doc, f"{number}. {title}", level=2)

    for line in lines:

        add_body(doc, line)


def main() -> None:

    doc = Document()

    style = doc.styles["Normal"]

    style.font.name = "Calibri"

    style.font.size = Pt(12)

    title = doc.add_heading("Cómo instalar la transcripción de audio en Windows", 0)

    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    add_body(
        doc,
        "Sirve para transcribir entrevistas y otros audios. "
        "El resultado es un archivo de Word, con párrafos, listo para revisar.",
    )

    add_body(
        doc,
        "No tiene que copiar carpetas a mano, ni abrir archivos de configuración, "
        "ni escribir rutas. Si su nombre de usuario lleva espacios "
        "(por ejemplo, Edith quijano), no importa: el instalador lo resuelve.",
        bold=True,
    )

    add_heading(doc, "Qué necesita", 1)

    add_body(doc, "Una computadora con Windows 10 u 11, internet la primera vez, y el audio que quiera transcribir (por ejemplo un .mp3).")

    add_step(
        doc,
        "1",
        "Descargue el programa",
        [
            "Abra el navegador (Edge o Chrome) y copie esta dirección:",
            ZIP_URL,
            "Se bajará un archivo comprimido (.zip). Casi siempre queda en la carpeta Descargas.",
        ],
    )

    add_step(
        doc,
        "2",
        "Ábralo",
        [
            "Vaya a Descargas.",
            "Clic derecho sobre el archivo cuyo nombre empieza por stt.",
            "Elija Extraer todo y después Extraer.",
            "Se abre una carpeta llamada stt-main. Entre en ella.",
        ],
    )

    add_step(
        doc,
        "3",
        "Instale con un doble clic",
        [
            "Dentro de stt-main, doble clic en Instalar.bat.",
            "Si Windows muestra un aviso azul (“protegió su PC”), pulse Más información y luego Ejecutar de todas formas.",
            "No escriba nada. Espere. La primera vez puede tardar varios minutos.",
            "Si Python o uv ya están en la computadora, el instalador los usa y no los vuelve a instalar.",
            "Cuando diga que la instalación terminó, puede cerrar esa ventana.",
        ],
    )

    add_step(
        doc,
        "4",
        "Transcriba un audio",
        [
            "En el Escritorio verá un icono llamado Transcribir.",
            "Arrastre el archivo de audio encima de ese icono.",
            "Se abre una ventana. Ahí se ve el avance y, en unas líneas, el texto que se va transcribiendo.",
            "La primera transcripción descarga el modelo de idioma y tarda más. Las siguientes, menos.",
            "Al terminar, el Word está en Documentos, dentro de la carpeta Transcripciones.",
            "Ábralo con Word para revisar, agregar saltos de línea y ajustar el formato.",
        ],
    )

    add_heading(doc, "Qué queda configurado solo", 1)

    for item in (
        "El texto se guarda en Word (.docx).",
        "La carpeta es Documentos\\Transcripciones.",
        "El idioma se detecta solo a partir del audio.",
        "El programa elige un modelo acorde a la memoria de esa computadora, para no dejarla lenta.",
        "Los párrafos se separan cuando hay una pausa en el audio.",
    ):

        paragraph = doc.add_paragraph(item, style="List Bullet")

        for run in paragraph.runs:

            run.font.size = Pt(12)

            run.font.name = "Calibri"

    add_heading(doc, "Si más adelante quiere otra carpeta", 1)

    add_body(
        doc,
        "En el Escritorio también queda Configurar-transcripcion. "
        "Doble clic, y ahí puede cambiar la carpeta o el formato. "
        "No hace falta para el uso de todos los días.",
    )

    add_heading(doc, "Si algo falla", 1)

    add_body(
        doc,
        "No cierre la ventana negra. Tome una foto del texto y envíela a quien le instaló el programa.",
    )

    doc.save(OUT)

    print(OUT)


if __name__ == "__main__":

    main()
