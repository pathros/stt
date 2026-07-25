# stt — Speech To Text

CLI de transcripción con [faster-whisper](https://github.com/SYSTRAN/faster-whisper).  
También descarga captions de YouTube y genera podcasts de audio a partir de guiones Markdown.

## Requisitos

- Python ≥ 3.12
- [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- macOS recomendado para el motor de podcast `say` (voces del sistema)

```bash
pip install -e .
```

## Cómo transcribir

### Menú interactivo

Sin argumentos abre el menú guiado:

```bash
stt
```

Opciones: archivo local · YouTube · podcast · configuración · salir.

### Archivo local

```bash
stt ~/Audio/entrevista.m4a
stt ~/Audio/entrevista.m4a -f md,srt -t
stt demo.wav --minutes 2          # solo los primeros 2 minutos
```

Extensiones reconocidas: `.mp3`, `.m4a`, `.opus`, `.wav`, `.flac`, `.aac`, `.ogg`, `.mp4`, `.mkv`, `.webm`.

Idioma desconocido: deja `-l auto` (default) o omítelo; Whisper lo detecta.  
Si ya sabes el código ISO: `-l es`, `-l uk`, `-l en`, etc.

### VAD (Voice Activity Detection)

**VAD** = detector de actividad de voz. Recorta silencios y tramos que no parecen habla, para acelerar y evitar basura.

| Tipo de audio | ¿Usar VAD? | Ejemplo |
|---------------|------------|---------|
| Reuniones (Zoom, Meet), entrevistas, podcasts hablados | **Sí** (default) | `stt reunion.m4a` |
| Canciones, música con letra, karaoke | **No** (`--no-vad`) | `stt cancion.wav -l uk --no-vad` |

En música el VAD suele tirar casi todo el audio (solo quedan 1–2 líneas). Con `--no-vad` también se evita condicionar en el texto previo, que en canciones produce alucinaciones típicas (“субтитры…”, “thanks for watching”, etc.).

```bash
# Reunión / podcast hablado (VAD activado)
stt ~/Downloads/zoom-call.m4a -l es -f md

# Canción en cualquier idioma
stt ~/Music/track.wav -l auto --no-vad
stt ~/Music/track.wav -l uk --no-vad -f txt,srt -t
```

### YouTube (video o playlist)

Primero intenta captions del video; si no hay, usa Whisper.

```bash
stt "https://www.youtube.com/watch?v=…"
stt youtube "https://youtu.be/…" -f txt,srt
stt "https://…" --whisper           # fuerza Whisper (ignora captions)
```

Si el enlace trae video y playlist, el menú pregunta qué procesar.

## Formatos de salida

| Formato | Descripción |
|---------|-------------|
| `txt`   | Texto plano (una línea por segmento) |
| `md`    | Markdown con párrafos por pausas |
| `srt`   | Subtítulos SubRip |
| `vtt`   | WebVTT |
| `json`  | Segmentos con `start` / `end` / `text` |

Varios a la vez: `-f md,srt,json`.  
`-t` / `--timestamps` añade marcas de tiempo donde aplique; `--no-timestamps` las omite.

Salida por defecto: `~/Downloads` (configurable).

## Podcast (texto → audio)

Genera un archivo de audio a partir de un guion `.md` con front matter YAML.

```bash
stt podcast guion.md
stt podcast guion.md -f m4a --rate 180
```

Formatos de audio: `m4a` (default), `mp3`, `wav`.

### Ejemplo de guion

```markdown
---
title: Mi episodio
language: es-MX
engine: say          # say (macOS) o edge (voces neuronales en línea)
pause: 0.4
voices:
  ANA: Paulina
  LUIS: Reed
---

**ANA:** Hola, bienvenidos al episodio de hoy.

**LUIS:** Gracias Ana. Empezamos con las noticias.
```

También acepta monólogo (`voice: Paulina`), `speakers:` / `speaker:` en el front matter, y etiquetas `[ANA]`, `ANA:` o `**ANA:**`.  
`[pausa]` / `[pause]` y encabezados cierran el turno actual.

| Motor   | Notas |
|---------|--------|
| `say`   | Voces de macOS. Por defecto: Paulina, Reed (variante del idioma del guion). |
| `edge`  | [edge-tts](https://github.com/rany2/edge-tts), requiere internet. Por defecto: `es-MX-DaliaNeural`, `es-MX-JorgeNeural`. |

## Flags globales

| Flag | Descripción |
|------|-------------|
| `-f`, `--format` | Formato(s) de salida (coma para varios) |
| `-t`, `--timestamps` | Incluir marcas de tiempo |
| `--no-timestamps` | Sin marcas de tiempo |
| `-m`, `--model` | Modelo Whisper (`tiny`, `medium`, `large-v3`, …) |
| `-l`, `--language` | Idioma (`es`, `en`, …) o `auto` |
| `-o`, `--output` | Carpeta de salida |
| `--minutes N` | Vista previa: solo los primeros N minutos (local) |
| `--whisper` | YouTube: forzar Whisper |
| `--no-vad` | Desactiva VAD (mejor para canciones/música) |
| `--rate N` | Podcast: palabras por minuto |

## Configuración

Archivo: `config/config.json`

```json
{
    "model": "large-v3",
    "language": "auto",
    "output": "~/Downloads",
    "formats": ["txt"],
    "beam_size": 5,
    "vad_filter": true,
    "compute_type": "int8"
}
```

Editable también desde el menú (`stt` → opción 4). Los flags de CLI sobrescriben la sesión actual sin guardar.
