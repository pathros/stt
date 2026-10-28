@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM Version fijada. No se sigue la rama main: si la cuenta cambiara,
REM esta huella deja de coincidir y la instalacion se detiene.
REM STT_SHA256 es la del ZIP de GitHub del tag (se publica en el release).
set "STT_TAG=v0.1.0"
set "STT_SHA256=pendiente"

REM Si este archivo no está junto al programa, lo descarga solo
REM en la carpeta del usuario (sirve aunque el nombre tenga espacios).
if not exist "%~dp0pyproject.toml" (
  echo.
  echo  Descargando la version %STT_TAG%. Hace falta internet.
  echo  Se comprueba la huella antes de instalar.
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$expected=([string]$env:STT_SHA256).ToLowerInvariant();" ^
    "$tag=[string]$env:STT_TAG;" ^
    "$dest=Join-Path $env:USERPROFILE 'Apps\stt';" ^
    "$zip=Join-Path $env:TEMP 'stt-release.zip';" ^
    "$url='https://github.com/pathros/stt/archive/refs/tags/' + $tag + '.zip';" ^
    "Invoke-WebRequest -Uri $url -OutFile $zip;" ^
    "$actual=(Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLowerInvariant();" ^
    "if ($actual -ne $expected) {" ^
    "  Remove-Item $zip -Force -ErrorAction SilentlyContinue;" ^
    "  Write-Error ('La descarga no coincide con la version publicada (' + $tag + '). Esperada: ' + $expected + ' Recibida: ' + $actual);" ^
    "  exit 1" ^
    "};" ^
    "$extract=Join-Path $env:TEMP 'stt-extract';" ^
    "if (Test-Path $extract) { Remove-Item $extract -Recurse -Force };" ^
    "Expand-Archive -Path $zip -DestinationPath $extract -Force;" ^
    "$dirs=@(Get-ChildItem -LiteralPath $extract -Directory);" ^
    "if ($dirs.Count -ne 1) { Write-Error 'El ZIP no trae una sola carpeta.'; exit 1 };" ^
    "New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null;" ^
    "if (Test-Path $dest) { Remove-Item $dest -Recurse -Force };" ^
    "Move-Item $dirs[0].FullName $dest;" ^
    "Remove-Item $zip -Force;" ^
    "Write-Output $dest"
  if errorlevel 1 goto :fail
  if not exist "%USERPROFILE%\Apps\stt\Instalar.bat" goto :fail
  call "%USERPROFILE%\Apps\stt\Instalar.bat"
  exit /b %ERRORLEVEL%
)

cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set "UV=%USERPROFILE%\.local\bin\uv.exe"

echo.
echo  Transcripcion de audio
echo  ======================
echo.
echo  No tiene que copiar carpetas ni editar archivos.
echo  El nombre de usuario puede llevar espacios.
echo  La primera vez necesita internet y puede tardar varios minutos.
echo.

call :locate_uv
if errorlevel 1 (
  echo No se encontro uv. Se instalara.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/0.13.6/install.ps1 | iex"
  set "UVCMD=%USERPROFILE%\.local\bin\uv.exe"
) else (
  echo uv ya esta instalado. No se vuelve a instalar.
)

if not exist "%UVCMD%" (
  echo.
  echo No se pudo preparar uv. Revise la conexion y vuelva a abrir Instalar.bat.
  goto :fail
)

call :locate_python
if errorlevel 1 (
  echo No hay Python 3.12 o mas reciente. Se instalara Python 3.12.
  "%UVCMD%" python install 3.12
  if errorlevel 1 goto :fail
  "%UVCMD%" python pin 3.12
  if errorlevel 1 goto :fail
) else (
  echo Python ya esta instalado. No se vuelve a instalar.
  "%UVCMD%" python pin 3.12 >nul 2>&1
  if errorlevel 1 "%UVCMD%" python pin 3.13 >nul 2>&1
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo.
  echo Instalando el programa que abre los audios...
  winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  echo.
) else (
  echo ffmpeg ya esta instalado.
)

echo.
echo Preparando el programa...
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
  "%UVCMD%" venv
  if errorlevel 1 goto :fail
)

"%UVCMD%" pip install -e .
if errorlevel 1 goto :fail

if not exist "%~dp0.venv\Scripts\stt.exe" goto :fail

echo.
echo Ajustando esta computadora. No escriba nada.
echo.

"%~dp0.venv\Scripts\stt.exe" configurar --auto
if errorlevel 1 goto :fail

echo.
echo Instalacion terminada.
echo.
echo En el Escritorio, arrastre el audio encima del icono Transcribir.
echo El Word queda en la carpeta Documentos, dentro de Transcripciones.
echo.
pause
exit /b 0

:fail
echo.
echo La instalacion no termino.
echo Deje esta ventana abierta y envie una foto del texto.
echo.
pause
exit /b 1

:locate_uv
set "UVCMD="
if exist "%USERPROFILE%\.local\bin\uv.exe" set "UVCMD=%USERPROFILE%\.local\bin\uv.exe"
if not defined UVCMD if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" set "UVCMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe"
if not defined UVCMD (
  for /f "delims=" %%U in ('where uv 2^>nul') do (
    if not defined UVCMD set "UVCMD=%%U"
  )
)
if not defined UVCMD exit /b 1
exit /b 0

:locate_python
"%UVCMD%" python find 3.12 >nul 2>&1
if not errorlevel 1 exit /b 0
"%UVCMD%" python find 3.13 >nul 2>&1
if not errorlevel 1 exit /b 0
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 exit /b 0
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 exit /b 0
python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0
exit /b 1
