@echo off
setlocal
REM Usuario con espacio: dejar SIEMPRE las comillas en STT_HOME / STT_EXE.
set "STT_HOME=C:\Users\Edith quijano\Apps\stt"
set "STT_EXE=%STT_HOME%\.venv\Scripts\stt.exe"

REM Avisos de Hugging Face en Windows (inofensivos; el modelo ya queda en cache).
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

cd /d "%STT_HOME%" 2>nul
if errorlevel 1 (
  echo.
  echo  ERROR: No existe la carpeta del programa:
  echo  %STT_HOME%
  echo.
  pause
  exit /b 1
)

if not exist "%STT_EXE%" (
  echo.
  echo  ERROR: No se encuentra stt.exe
  echo  %STT_EXE%
  echo.
  echo  Falta el paso de instalacion. Abre PowerShell y ejecuta:
  echo    cd "C:\Users\Edith quijano\Apps\stt"
  echo    uv pip install -e .
  echo    dir .\.venv\Scripts\stt.exe
  echo.
  pause
  exit /b 1
)

if "%~1"=="" (
  echo.
  echo  Arrastra un archivo de audio o video encima de este icono.
  echo  Ejemplo: un .mp3
  echo.
  pause
  exit /b 1
)

"%STT_EXE%" "%~1" -l es -f docx
echo.
pause
