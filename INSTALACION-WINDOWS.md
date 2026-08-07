# Instalación de `stt` (transcripción) en Windows 11

Guía para instalar `stt` en una PC con Windows (por ejemplo la de la secretaria: Dell / i5-14500 / 16 GB RAM).  
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
[ ] Crear entorno e instalar el programa
[ ] Ajustar config.json (medium + es) — output con / o \\, NUNCA una sola \
[ ] Crear Transcribir.bat (solo arrastrar MP3)
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

Tiempos aproximados:

| Paso | Tiempo |
|------|--------|
| `uv python install 3.12` | 1–3 min |
| `uv pip install -e .` | 2–10 min |

Verificar que el comando existe:

```powershell
uv run stt --help
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
    "formats": ["txt", "md"],
    "beam_size": 5,
    "vad_filter": true,
    "compute_type": "int8"
}
```

Misma ruta con `\\` (también válido):

```json
{
    "model": "medium",
    "language": "es",
    "output": "C:\\Users\\Secre-alag1\\Documents\\Transcripciones",
    "formats": ["txt", "md"],
    "beam_size": 5,
    "vad_filter": true,
    "compute_type": "int8"
}
```

Si prefieres Descargas y no quieres crear carpeta:

```json
{
    "model": "medium",
    "language": "es",
    "output": "~/Downloads",
    "formats": ["txt", "md"],
    "beam_size": 5,
    "vad_filter": true,
    "compute_type": "int8"
}
```

4. Guarda (Ctrl+S) y cierra. Vuelve a abrir el archivo y confirma que en `output` no quedó ninguna `\` suelta.

---

## 7. Un solo acceso: arrastrar el MP3

Basta **un** acceso en el Escritorio: arrastras el `.mp3` encima del icono.

1. Escritorio → clic derecho → Nuevo → Documento de texto.
2. Nómbralo `Transcribir.bat` (extensión `.bat`, no `.txt`).
3. Clic derecho → Editar, pega **exactamente**:

```bat
@echo off
cd /d C:\Users\Secre-alag1\Apps\stt
if "%~1"=="" (
  echo.
  echo  Arrastra un archivo de audio o video encima de este icono.
  echo  Ejemplo: un .mp3
  echo.
  pause
  exit /b 1
)
uv run stt "%~1" -l es -f txt,md
echo.
pause
```

(Cambia `Secre-alag1` por el usuario de esta PC antes de guardar.)

4. Guarda y cierra.

**Uso:** arrastra `Agricultura_organica_Riesgos_y_beneficios.mp3` (o cualquier audio) **encima** de `Transcribir.bat`.

Si solo haces doble clic sin arrastrar, te avisará que hay que soltar un archivo.

---

## 8. Pruebas

### 8.1 Corregir config y probar 1 minuto del MP3

Tras arreglar `config.json`:

```powershell
cd C:\Users\Secre-alag1\Apps\stt
```

```powershell
uv run stt "C:\Users\Secre-alag1\Downloads\Agricultura_organica_Riesgos_y_beneficios.mp3" -l es -f txt,md --minutes 1
```

La **primera** vez con `medium` descarga ~1.5 GB del modelo (**5–20 min** según internet).  
**No cierres** la ventana. Luego transcribe solo 1 minuto.

Revisa el `.txt` / `.md` en:

```text
C:\Users\Secre-alag1\Documents\Transcripciones
```

(o en Descargas si usaste `~/Downloads`).

### 8.2 Solo 2 minutos (misma idea)

```powershell
uv run stt "C:\Users\Secre-alag1\Downloads\Agricultura_organica_Riesgos_y_beneficios.mp3" -l es -f txt,md --minutes 2
```

### 8.3 Archivo completo

Cuando ya confíen en la calidad:

- Arrastra el MP3 encima de `Transcribir.bat`, **o**

```powershell
uv run stt "C:\Users\Secre-alag1\Downloads\Agricultura_organica_Riesgos_y_beneficios.mp3" -l es -f txt,md
```

**Expectativa:** ~2 h de audio en CPU con `medium` puede tardar **alrededor de la duración del audio** (a veces más). PC enchufada, sin suspensión.

---

## 9. Uso diario (para la secretaria)

1. Localizar el `.mp3` en el Explorador.
2. Arrastrarlo encima de **Transcribir** (Escritorio).
3. Esperar; el texto sale en `Documents\Transcripciones` (`.txt` y `.md`).
4. La primera vez tarda más (descarga del modelo); después solo carga y transcribe.

---

## 10. Problemas frecuentes

| Síntoma | Qué hacer |
|---------|-----------|
| `Invalid \escape` / `config.json inválido` | En Windows, `"output"` con `/` o `\\`; **una sola `\` truena** (pasó en la PC de Edith). Ver aviso al inicio y sección 6 |
| Rutas “no se encuentra” al pegar comandos | El usuario de la guía (`Secre-alag1`) no es el de esa PC → usa `$env:USERNAME` |
| `uv` no se reconoce | Nueva terminal o reiniciar Windows |
| `ffmpeg` no se reconoce | Nueva terminal tras `winget`; `ffmpeg -version` |
| Parece congelado en la 1ª corrida | Descarga del modelo; esperar |
| PC muy lenta con Office + `medium` | En `config.json`: `"model": "small"` |
| Doble clic en el bat sin archivo | Es normal: hay que **arrastrar** el MP3 encima |
| OneDrive interfiere | Proyecto en `C:\Users\...\Apps\stt`, no en OneDrive |

---

## 11. Actualizar el programa más adelante

```powershell
cd C:\Users\Secre-alag1\Apps\stt
uv pip install -e .
```

---

## Resumen de rutas

Sustituye `Secre-alag1` / `TU_USUARIO` por el de **esa** computadora (`$env:USERNAME`).

| Qué | Ruta (ejemplo) |
|-----|----------------|
| Proyecto | `C:\Users\TU_USUARIO\Apps\stt` |
| Config | `C:\Users\TU_USUARIO\Apps\stt\config\config.json` |
| Salida en JSON (`output`) | `C:/Users/TU_USUARIO/Documents/Transcripciones` (con `/`, no `\`) |
| Acceso (único) | Escritorio → `Transcribir.bat` (arrastrar MP3) |

Modelo: **`medium`** · idioma **`es`** · compute **`int8`**.
