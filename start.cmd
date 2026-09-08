@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -m renamer
if errorlevel 1 (
    echo.
    echo Startup failed. See the error above and README.md.
    pause
)
exit /b
:missing
echo Project Python environment is missing. See README.md for setup.
pause
exit /b 1
