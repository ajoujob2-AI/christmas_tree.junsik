@echo off
setlocal
cd /d "%~dp0"

set "PY_LAUNCHER=py"
where py >nul 2>nul
if errorlevel 1 set "PY_LAUNCHER=python"

%PY_LAUNCHER% --version >nul 2>nul
if errorlevel 1 (
  echo Python could not be found. Install Python and try again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the local Python environment...
  %PY_LAUNCHER% -m venv .venv
  if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -c "import numpy, pygame, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing the required packages for the first run...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" christmas_tree.py --full
exit /b %errorlevel%

:failed
echo.
echo Installation failed. Check the internet connection and try again.
pause
exit /b 1
