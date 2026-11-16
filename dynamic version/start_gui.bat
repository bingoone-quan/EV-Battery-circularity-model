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

%PY_CMD% -m streamlit --version >nul 2>nul
if errorlevel 1 (
    echo Streamlit is not installed. Installing it for the current user...
    %PY_CMD% -m pip --version >nul 2>nul
    if errorlevel 1 (
        %PY_CMD% -m ensurepip --upgrade
        if errorlevel 1 goto install_failed
    )
    %PY_CMD% -m pip install --user streamlit
    if errorlevel 1 goto install_failed
    %PY_CMD% -m streamlit --version >nul 2>nul
    if errorlevel 1 goto install_failed
)

echo Starting the dynamic GUI...
%PY_CMD% -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo The GUI exited with an error. See the message above.
    pause
)
exit /b

:install_failed
echo.
echo Streamlit installation failed. Check your internet connection and Python setup, then try again.
pause
exit /b 1
