@echo off
REM Double-click this to open Anthem.
REM pythonw runs the window with no console box behind it.

setlocal
cd /d "%~dp0"

where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw "%~dp0gui.py"
    goto :eof
)

where python >nul 2>&1
if %errorlevel%==0 (
    python "%~dp0gui.py"
    goto :eof
)

echo Python was not found on this PC.
echo Install it from https://www.python.org/downloads/ and tick
echo "Add python.exe to PATH" during setup, then run this again.
pause
