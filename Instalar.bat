@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM Si este archivo no está junto al programa, lo descarga solo
REM en la carpeta del usuario (sirve aunque el nombre tenga espacios).
if not exist "%~dp0pyproject.toml" (
  echo.
  echo  Descargando el programa. Hace falta internet.
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$dest=Join-Path $env:USERPROFILE 'Apps\stt';" ^
    "$zip=Join-Path $env:TEMP 'stt-main.zip';" ^
    "Invoke-WebRequest -Uri 'https://github.com/pathros/stt/archive/refs/heads/main.zip' -OutFile $zip;" ^
    "$extract=Join-Path $env:TEMP 'stt-extract';" ^
    "if (Test-Path $extract) { Remove-Item $extract -Recurse -Force };" ^
    "Expand-Archive -Path $zip -DestinationPath $extract -Force;" ^
    "$inner=Join-Path $extract 'stt-main';" ^
    "New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null;" ^
    "if (Test-Path $dest) { Remove-Item $dest -Recurse -Force };" ^
    "Move-Item $inner $dest;" ^
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

if not exist "%UV%" (
  where uv >nul 2>&1
  if errorlevel 1 (
    echo Instalando el asistente de Python...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  )
)

if exist "%UV%" (
  set "UVCMD=%UV%"
) else (
  set "UVCMD=uv"
)

"%UVCMD%" --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo No se pudo preparar Python. Revise la conexion y vuelva a abrir Instalar.bat.
  goto :fail
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo.
  echo Instalando el programa que abre los audios...
  winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  echo.
)

echo Preparando el programa...
echo.

"%UVCMD%" python install 3.12
if errorlevel 1 goto :fail

"%UVCMD%" python pin 3.12
if errorlevel 1 goto :fail

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
