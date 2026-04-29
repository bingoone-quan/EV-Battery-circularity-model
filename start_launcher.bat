@echo off
setlocal

cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py"

if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo Python was not found on this computer.
    echo Please install Python first, then try again.
    pause
    exit /b 1
)

%PY_CMD% launcher.py

if errorlevel 1 (
    echo.
    echo The launcher exited with an error. See the message above.
    pause
)
