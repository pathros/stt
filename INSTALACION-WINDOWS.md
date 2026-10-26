# Instalación de `stt` (transcripción) en Windows 11

## Instalación fácil (recomendada)

Instrucciones para imprimir o enviar: **`INSTALACION-WINDOWS.docx`** (en esta misma carpeta).

No hay que copiar archivos a mano, ni editar `config.json`, ni escribir la ruta del usuario. Si el nombre lleva espacios (`Edith quijano`), el instalador lo resuelve.

1. Descargue el ZIP: https://github.com/pathros/stt/archive/refs/heads/main.zip
2. Clic derecho → **Extraer todo**.
3. Entre en la carpeta `stt-main` y doble clic en **`Instalar.bat`**.
4. Espere (internet la primera vez). No escriba nada. Si Python o uv ya están instalados, los usa y no los vuelve a instalar.
5. En el Escritorio, arrastre el audio encima de **Transcribir**.

El texto queda en **Documentos\Transcripciones**, en Word, en párrafos. El idioma se detecta solo. El modelo se elige según la memoria de esa PC.

Para cambiar la carpeta más adelante: doble clic en **Configurar-transcripcion** (Escritorio).

La guía larga de abajo es el camino manual, por si el doble clic no basta.

---

Guía manual para instalar `stt` en una PC con Windows (por ejemplo la de la secretaria: Dell / i5-14500 / 16 GB RAM).  
Abre este archivo en el Bloc de notas o en el navegador y **copia/pega** los comandos en **PowerShell**.

---

## Antes de empezar: tu nombre de usuario de Windows

En esta guía aparece `Secre-alag1` solo como **ejemplo**.  
**El nombre de usuario cambia en cada computadora** (en la PC de Edith será otro, en otra oficina otro distinto).

Averígualo en PowerShell:

```powershell
$env:USERNAME
```

O mira la carpeta en el Explorador:

```text
C:\Users\
```

Ahí verás carpetas con cada usuario. Usa **el de esa PC** en todas las rutas de esta guía: proyecto, `config.json`, `Transcribir.bat` y pruebas.

| En la guía (ejemplo) | En tu PC (sustituye) |
|----------------------|----------------------|
| `Secre-alag1` | el resultado de `$env:USERNAME` |

Si el usuario tiene **espacios** (ej. `Edith quijano`), en PowerShell y en el `.bat` las rutas van **entre comillas**:

```powershell
cd "C:\Users\Edith quijano\Apps\stt"
```

En JSON (`config.json`) usa `/` y no hace falta escapar el espacio:

```json
"output": "C:/Users/Edith quijano/Documents/Transcripciones"
```

Si copias/pegas sin cambiar el usuario, las rutas no existirán y fallará la instalación.

---

## Atención: `config.json` y la barra `\` en Windows

En Windows es normal escribir rutas con **diagonal inversa** `\`:

```text
C:\Users\Alguien\Documents\Transcripciones
```

Pero **`config.json` no es una ruta de Windows: es JSON**. En JSON, `\` inicia un “escape” (`\n`, `\t`, etc.).  
Una sola `\` delante de `Users` (**truena** / rompe el archivo):

```text
json.decoder.JSONDecodeError: Invalid \escape
```

Eso pasó al instalar en la PC Windows de Edith: el programa no arrancaba hasta corregir `output`.

En el campo `"output"` de `config.json` usa **una** de estas formas:

| Forma | Ejemplo | ¿OK? |
|-------|---------|------|
| Diagonal normal `/` (recomendado) | `"C:/Users/TU_USUARIO/Documents/Transcripciones"` | Sí |
| Doble diagonal inversa `\\` | `"C:\\Users\\TU_USUARIO\\Documents\\Transcripciones"` | Sí |
| Una sola `\` | `"C:\Users\TU_USUARIO\..."` | **No — truena** |

En PowerShell o el Explorador puedes seguir usando `\`; el cuidado es **solo al editar `config.json`**. Detalle y plantilla en la [sección 6](#6-configurar-modelo-medium--español).

---

## Checklist rápida

```text
[ ] Anotar el usuario de ESTA PC ($env:USERNAME) y reemplazar Secre-alag1 en todas las rutas
[ ] Copiar proyecto de la USB a C:\Users\TU_USUARIO\Apps\stt
[ ] Verificar espacio en disco (≥ 10 GB libres)
[ ] Instalar uv
[ ] Instalar ffmpeg
[ ] Crear entorno: uv python install / pin / venv
[ ] **uv pip install -e .** y verificar `.venv\Scripts\stt.exe`
[ ] Ajustar config.json (medium + es) — output con / o \\, NUNCA una sola \
[ ] Crear Transcribir.bat que llama a stt.exe (NO uv run)
[ ] Probar con --minutes 1 del MP3
```

---

## 0. Copiar archivos desde la USB

1. Inserta la USB.
2. Abre la carpeta `stt-instalacion\faster-whisper` de la USB.
3. En el Explorador de archivos ve a (cambia `Secre-alag1` por **tu** usuario):

```text
C:\Users\Secre-alag1\
```

4. Crea la carpeta `Apps` (si no existe).
5. Dentro de `Apps`, crea la carpeta `stt`.
6. Copia **todo el contenido** de `faster-whisper` (de la USB) dentro de:

```text
C:\Users\Secre-alag1\Apps\stt
```

Debe quedar así (aprox.):

```text
C:\Users\Secre-alag1\Apps\stt\
  ├── config\
  │   └── config.json
  ├── src\
  ├── pyproject.toml
  ├── README.md
  └── INSTALACION-WINDOWS.md
```

---

## 1. Abrir PowerShell

- Clic derecho en el menú Inicio → **Windows PowerShell** o **Terminal**.
- O busca “PowerShell” y ábrelo **sin admin** (salvo que la empresa lo exija).

---

## 2. Verificar espacio en disco

```powershell
Get-PSDrive C | Format-List Used,Free
```

Con **10 GB libres o más** es suficiente.

---

## 3. Instalar `uv` (gestor de Python; no instalar Python global)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Cierra PowerShell por completo**, abre uno nuevo, y verifica:

```powershell
uv --version
```

Si dice que no reconoce `uv`, cierra sesión de Windows o reinicia y vuelve a probar.

---

## 4. Instalar ffmpeg (obligatorio para MP3)

```powershell
winget install Gyan.FFmpeg
```

Cierra PowerShell, abre uno nuevo, y verifica:

```powershell
ffmpeg -version
```

Debe mostrar la versión. Sin ffmpeg, muchos `.mp3` fallan.

---

## 5. Crear entorno e instalar el programa

Copia y pega **bloque por bloque** (sustituye `Secre-alag1` por tu usuario de esta PC):

```powershell
cd C:\Users\Secre-alag1\Apps\stt
```

```powershell
uv python install 3.12
```

```powershell
uv python pin 3.12
```

```powershell
uv venv
```

```powershell
uv pip install -e .
```

**Este paso es obligatorio.** Sin él no existe `stt.exe` y el acceso directo falla con errores del tipo `could not spawn stt` / `not found`.

Tiempos aproximados:

| Paso | Tiempo |
|------|--------|
| `uv python install 3.12` | 1–3 min |
| `uv pip install -e .` | 2–10 min |

### Verificación (no saltar)

En la misma carpeta del proyecto:

```powershell
cd C:\Users\Secre-alag1\Apps\stt
dir .venv\Scripts\stt.exe
```

Debe listar el archivo `stt.exe`. Si dice que no existe, repite `uv pip install -e .`.

Prueba en PowerShell (sí puede usar `uv run` aquí):

```powershell
uv run stt --help
```

o, más fiable (igual que el `.bat`):

```powershell
.\.venv\Scripts\stt.exe --help
```
---

## 6. Configurar modelo (`medium` + español)

### Por qué “truena” el `config.json` en Windows / PowerShell

Windows y PowerShell usan `\` en rutas. Eso está bien en el Explorador y en comandos como:

```powershell
cd C:\Users\Secre-alag1\Apps\stt
```

Pero al editar **`config\config.json`**, el valor de `"output"` se interpreta como **JSON**, no como ruta de Windows.  
Una sola diagonal inversa `\` **rompe** el archivo (caso visto en la PC de Edith):

```text
json.decoder.JSONDecodeError: Invalid \escape
```

o el mensaje del programa:

```text
config.json inválido (...): ...
En Windows, en "output" usa barras / ... o dobles \\
```

**Regla:** en `"output"` nunca una sola `\`. Usa `/` o `\\`.

| Incorrecto (truena) | Correcto |
|---------------------|----------|
| `"C:\Users\Secre-alag1\Documents\Transcripciones"` | `"C:/Users/Secre-alag1/Documents/Transcripciones"` |
| | o `"C:\\Users\\Secre-alag1\\Documents\\Transcripciones"` |
| | o `"~/Downloads"` |

Sustituye `Secre-alag1` por el usuario de **esa** computadora.

### Archivo correcto

1. (Opcional) Crea la carpeta de salida (aquí sí puedes usar `\` en el Explorador):

```text
C:\Users\Secre-alag1\Documents\Transcripciones
```

2. Abre con el Bloc de notas:

```text
C:\Users\Secre-alag1\Apps\stt\config\config.json
```

3. **Borra todo** y pega esto (usa `/` en `output`; cambia el usuario):

```json
{
    "model": "medium",
    "language": "es",
    "output": "C:/Users/Secre-alag1/Documents/Transcripciones",
    "formats": ["docx"],
    "beam_size": 2,
    "vad_filter": true,
    "compute_type": "int8",
    "initial_prompt": "",
    "batch_size": 8
}
```

- **`docx`**: Word abre el archivo directo (recomendado en esta PC).
- **`beam_size`: 2**: más rápido que 5 en CPU; calidad casi igual en dictados claros (alternativa: `3`).
- **`batch_size`: 8**: acelera reuniones/habla (con VAD). Pon `0` solo si hay problemas.
- Opcional: `"formats": ["docx", "txt"]` si también quieren un `.txt` con párrafos.

Misma ruta con `\\` (también válido):

```json
{
    "model": "medium",
    "language": "es",
    "output": "C:\\Users\\Secre-alag1\\Documents\\Transcripciones",
    "formats": ["docx"],
    "beam_size": 2,
    "vad_filter": true,
    "compute_type": "int8",
    "initial_prompt": "",
    "batch_size": 8
}
```

Si prefieres Descargas y no quieres crear carpeta:

```json
{
    "model": "medium",
    "language": "es",
    "output": "~/Downloads",
    "formats": ["docx"],
    "beam_size": 2,
    "vad_filter": true,
    "compute_type": "int8",
    "initial_prompt": "",
    "batch_size": 8
}
```

4. Guarda (Ctrl+S) y cierra. Vuelve a abrir el archivo y confirma que en `output` no quedó ninguna `\` suelta.

---

## 7. Un solo acceso: arrastrar el MP3

**No uses `uv run` en el `.bat` del Escritorio.** Al arrastrar un archivo, Windows abre la consola con un PATH incompleto y aparece `could not spawn stt` / `not found`. El acceso debe llamar a `stt.exe` dentro de `.venv`.

### Opción A (recomendada): copiar el `.bat` del proyecto

1. En el proyecto ya viene `Transcribir.bat`.
2. Ábrelo con Bloc de notas y cambia `Secre-alag1` por el usuario de **esta** PC en la línea `STT_HOME`.
3. Cópialo al **Escritorio**.

### Opción B: crearlo a mano en el Escritorio

1. Escritorio → clic derecho → Nuevo → Documento de texto.
2. Nómbralo `Transcribir.bat` (extensión `.bat`, no `.txt`).
3. Clic derecho → Editar, pega **exactamente** (cambia el usuario):

```bat
@echo off
setlocal
set "STT_HOME=C:\Users\Edith quijano\Apps\stt"
set "STT_EXE=%STT_HOME%\.venv\Scripts\stt.exe"

cd /d "%STT_HOME%" 2>nul
if errorlevel 1 (
  echo ERROR: No existe %STT_HOME%
  pause
  exit /b 1
)

if not exist "%STT_EXE%" (
  echo ERROR: No se encuentra stt.exe
  echo Ejecuta en PowerShell:
  echo   cd "C:\Users\Edith quijano\Apps\stt"
  echo   uv pip install -e .
  echo   dir .\.venv\Scripts\stt.exe
  pause
  exit /b 1
)

if "%~1"=="" (
  echo Arrastra un archivo .mp3 encima de este icono.
  pause
  exit /b 1
)

"%STT_EXE%" "%~1" -l es -f docx
echo.
pause
```

(El espacio en `Edith quijano` está bien; las comillas de `set "STT_HOME=..."` lo protegen.)
4. Guarda y cierra.

**Uso:** arrastra el `.mp3` **encima** de `Transcribir.bat`.

Si solo haces doble clic sin arrastrar, te avisará que hay que soltar un archivo.  
Si falta la instalación, el propio `.bat` te dirá que ejecutes `uv pip install -e .`.

---

## 8. Pruebas

### 8.1 Corregir config y probar 1 minuto del MP3

Tras arreglar `config.json`:

```powershell
cd C:\Users\Secre-alag1\Apps\stt
```

```powershell
uv run stt "C:\Users\Secre-alag1\Downloads\Agricultura_organica_Riesgos_y_beneficios.mp3" -l es -f docx --minutes 1
```

La **primera** vez con `medium` descarga ~1.5 GB del modelo (**5–20 min** según internet).  
**No cierres** la ventana. Luego transcribe solo 1 minuto.

Revisa el `.docx` en:

```text
C:\Users\Secre-alag1\Documents\Transcripciones
```

(o en Descargas si usaste `~/Downloads`). Ábrelo con Word.

### 8.2 Solo 2 minutos (misma idea)

```powershell
uv run stt "C:\Users\Secre-alag1\Downloads\Agricultura_organica_Riesgos_y_beneficios.mp3" -l es -f docx --minutes 2
```

### 8.3 Archivo completo

Cuando ya confíen en la calidad:

- Arrastra el MP3 encima de `Transcribir.bat`, **o**

```powershell
uv run stt "C:\Users\Secre-alag1\Downloads\Agricultura_organica_Riesgos_y_beneficios.mp3" -l es -f docx
```

**Expectativa:** ~2 h de audio en CPU con `medium` puede tardar **alrededor de la duración del audio** (a veces más). PC enchufada, sin suspensión.

---

## 9. Uso diario (para la secretaria)

1. Localizar el `.mp3` en el Explorador.
2. Arrastrarlo encima de **Transcribir** (Escritorio).
3. Esperar; el resultado sale en `Documents\Transcripciones` como **`.docx`** (abrir con Word).
4. La primera vez tarda más (descarga del modelo); después solo carga y transcribe.

Un audio de ~2 h con `medium` en CPU puede tardar **cerca de 2 h o más**: es normal en i5 sin GPU.

---

## 10. Problemas frecuentes

| Síntoma | Qué hacer |
|---------|-----------|
| `could not spawn stt` / `not found` al usar el `.bat` | 1) Verificar `dir C:\Users\...\Apps\stt\.venv\Scripts\stt.exe`. Si no existe: `uv pip install -e .`. 2) Reemplazar el `.bat` del Escritorio por el que llama a `stt.exe` (sección 7), no `uv run stt`. |
| `open() got an unexpected keyword argument 'metadata_errors'` | Librería de audio demasiado nueva. En la carpeta del programa: `uv pip install "av>=11,<19"` y vuelva a arrastrar el audio. |
| La transcripción va lenta | En `config\config.json`, baje `"batch_size"` de `8` a `4`. Si sigue pesada, `2`. `0` apaga los lotes. |
| `Invalid \escape` / `config.json inválido` | En Windows, `"output"` con `/` o `\\`; **una sola `\` truena**. Ver sección 6 |
| Rutas “no se encuentra” al pegar comandos | El usuario de la guía no es el de esa PC → `$env:USERNAME` |
| `uv` no se reconoce | Nueva terminal o reiniciar Windows |
| `ffmpeg` no se reconoce | Nueva terminal tras `winget`; `ffmpeg -version` |
| Parece congelado en la 1ª corrida | Descarga del modelo; esperar |
| PC muy lenta / audio de muchas horas | `"beam_size": 2` o `"model": "small"` |
| “No puntúa” | Whisper sí puntúa; abrir el `.docx` nuevo. Si sigue plano, subir a `medium` (no `tiny`) |
| `No module named 'docx'` | Falta dependencia: `uv pip install -e .` |
| Doble clic en el bat sin archivo | Hay que **arrastrar** el MP3 encima |
| OneDrive interfiere | Proyecto en `C:\Users\...\Apps\stt`, no en OneDrive |

---

## 11. Actualizar el programa más adelante

Cuando haya cambios de código **y** nuevas dependencias (p. ej. Word):

1. Copiar los `.py` / `pyproject.toml` actualizados (sin pisar `config\config.json` ni `.venv`).
2. En PowerShell:

```powershell
cd C:\Users\Secre-alag1\Apps\stt
uv pip install -e .
```

3. Ajustar `config.json` / `Transcribir.bat` si la guía lo indica (p. ej. `-f docx`).

---

## Resumen de rutas

Sustituye `Secre-alag1` / `TU_USUARIO` por el de **esa** computadora (`$env:USERNAME`).

| Qué | Ruta (ejemplo) |
|-----|----------------|
| Proyecto | `C:\Users\TU_USUARIO\Apps\stt` |
| Config | `C:\Users\TU_USUARIO\Apps\stt\config\config.json` |
| Salida en JSON (`output`) | `C:/Users/TU_USUARIO/Documents/Transcripciones` (con `/`, no `\`) |
| Acceso (único) | Escritorio → `Transcribir.bat` (arrastrar MP3 → `.docx`) |

Modelo: **`medium`** · idioma **`es`** · `beam_size` **`2`** · `batch_size` **`8`** · formato **`docx`** · compute **`int8`**.
