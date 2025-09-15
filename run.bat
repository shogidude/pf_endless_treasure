@echo off
setlocal enabledelayedexpansion

rem Simple launcher for Windows: creates venv, installs deps, runs the app.
rem Usage:
rem   run.bat                   (uses .\cards if present)
rem   run.bat --cards .\cards   (or pass any args through)

set VENV_DIR=%VENV_DIR%
if "%VENV_DIR%"=="" set VENV_DIR=.venv

if not defined PYTHON set PYTHON=python

if not exist "%VENV_DIR%" (
  echo [setup] Creating virtual environment in %VENV_DIR%
  %PYTHON% -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

python -m pip install --upgrade pip >NUL
pip install -r requirements.txt

if "%~1"=="" (
  if exist "cards" (
    python endless_treasure.py --cards .\cards
  ) else (
    python endless_treasure.py
  )
) else (
  python endless_treasure.py %*
)

endlocal

