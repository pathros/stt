@echo off
setlocal
REM Este archivo vive DENTRO de la carpeta del programa.
REM El icono del Escritorio lo crea Instalar.bat (no copie este a mano).
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "STT_HOME=%~dp0"
set "STT_EXE=%STT_HOME%\.venv\Scripts\stt.exe"

cd /d "%STT_HOME%" 2>nul
if not exist "%STT_EXE%" (
  echo.
  echo  Primero abra Instalar.bat, en esta misma carpeta.
  echo.
  pause
  exit /b 1
)

if "%~1"=="" (
  echo.
  echo  Arrastre un archivo de audio encima de este icono.
  echo.
  pause
  exit /b 1
)

"%STT_EXE%" "%~1"
echo.
pause
