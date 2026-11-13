@echo off
REM BioLabCalc ELN & Multi-Modal LIMS Environment Configuration Batch Launcher
setlocal

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3 "%~dp0configure.py" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python "%~dp0configure.py" %*
    exit /b %ERRORLEVEL%
)

echo Error: Python 3 was not found in PATH.
exit /b 1
