@echo off
REM ============================================================================
REM BioLabCalc ELN & Multi-Modal LIMS Environment Configuration Batch Launcher
REM ============================================================================
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"

REM Resolve Python 3 executable: python-embed -> .venv -> py -3 -> non-WindowsApps python -> python3
if exist "%SCRIPT_DIR%python-embed\python.exe" (
    set "PYTHON_EXE="%SCRIPT_DIR%python-embed\python.exe""
    goto :found_python
)
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE="%SCRIPT_DIR%.venv\Scripts\python.exe""
    goto :found_python
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=py -3"
    goto :found_python
)

for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        set "PYTHON_EXE="%%I""
        goto :found_python
    )
)

where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=python3"
    goto :found_python
)

echo [!] Error: Python 3.8+ was not found on this system. >&2
if not defined CI pause
exit /b 1

:found_python
%PYTHON_EXE% "%SCRIPT_DIR%configure.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    if not defined CI pause
)
exit /b %EXIT_CODE%
