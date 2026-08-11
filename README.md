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
stt "https://…" --with-most-rated-comments      # top 10 comentarios (default)
stt "https://…" --with-most-rated-comments 25   # top N configurable
```

Si el enlace trae video y playlist, el menú pregunta qué procesar.  
Con `--with-most-rated-comments`, en playlists se guardan los comentarios top de **cada** video (`*-comments.md` junto a la transcripción).

## Formatos de salida

| Formato | Descripción |
|---------|-------------|
| `txt`   | Texto plano en párrafos (apto para Word: sin salto por cada frase) |
| `md`    | Markdown con párrafos por pausas |
| `docx`  | Documento Microsoft Word (abre directo en Word) |
| `srt`   | Subtítulos SubRip |
| `vtt`   | WebVTT |
| `json`  | Segmentos con `start` / `end` / `text` |

Varios a la vez: `-f md,srt,json` o `-f docx`.  
`-t` / `--timestamps` añade marcas de tiempo donde aplique; `--no-timestamps` las omite.

En macOS el default es `md`. En Windows de oficina conviene `docx` (configurable).

Salida por defecto: `~/Downloads` (configurable).

### Rendimiento y puntuación (CPU)

Whisper **sí puntúa** de fábrica (`medium` / `large-v3`). Si el texto “parece sin puntuación”, suele ser por mirar salidas muy fragmentadas o un modelo más chico (`tiny`/`base`).

En CPU (p. ej. i5 + 16 GB) un audio de ~2 h con `medium` puede tardar **cerca de la duración del audio** (a veces más): es esperado.

| Ajuste | Efecto |
|--------|--------|
| `model`: `small` | Más rápido, algo menos calidad/puntuación |
| `model`: `medium` | Equilibrio recomendado en oficina |
| `beam_size`: `2` | Buen atajo de velocidad; poca pérdida vs `5` |
| `beam_size`: `5` | Un poco mejor, más lento |
| `batch_size`: `8` | Lotes en CPU (habla + VAD); suele ~1.5–2× |
| `batch_size`: `0` | Desactiva lotes (p. ej. depuración) |
| `language`: `es` | Más estable/rápido que `auto` si el audio es español |
| `vad_filter`: `true` | Salta silencios (recomendado en habla) |
| `--no-vad` | Canciones/música; sin lotes (el batch necesita VAD) |

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
| `--with-most-rated-comments [N]` | YouTube: top N comentarios por likes (default 10; también en playlists) |
| `--no-vad` | Desactiva VAD (mejor para canciones/música) |
| `--rate N` | Podcast: palabras por minuto |

## Configuración

Archivo: `config/config.json`

```json
{
    "model": "large-v3",
    "language": "auto",
    "output": "~/Downloads",
    "formats": ["md"],
    "beam_size": 5,
    "vad_filter": true,
    "compute_type": "int8",
    "initial_prompt": "",
    "batch_size": 8
}
```

`initial_prompt` vacío: si el idioma es `es`, se usa una guía breve de puntuación.  
`batch_size` > 0 acelera habla con VAD; con `--no-vad` (canciones) se ignora y va en modo secuencial.

Editable también desde el menú (`stt` → opción 4). Los flags de CLI sobrescriben la sesión actual sin guardar.
