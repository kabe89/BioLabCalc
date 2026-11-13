@echo off
REM BioLabCalc Standalone CLI Batch Launcher for Windows
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3 "%SCRIPT_DIR%run.py" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python "%SCRIPT_DIR%run.py" %*
    exit /b %ERRORLEVEL%
)

echo Error: Python 3 was not found in PATH. >&2
exit /b 1
