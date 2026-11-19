@echo off
REM ============================================================================
REM BioLabCalc Standalone Batch Launcher for Windows Workstations
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
echo     Please install Python 3 or place a portable embed in python-embed\ >&2
if not defined CI pause
exit /b 1

:found_python
if "%~1"=="" goto :menu

%PYTHON_EXE% "%SCRIPT_DIR%run.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    if not defined CI pause
)
exit /b %EXIT_CODE%

:menu
echo ============================================================================
echo   BioLabCalc - Molecular Biology ^& Biophysics Workbench
echo ============================================================================
echo   1. Launch Lab Notebook (ELN)
echo   2. Interactive Gel Annotator
echo   3. Interactive Plasmid Workbench
echo   4. Run Setup Wizard
echo   5. CLI Help
echo   0. Exit
echo ============================================================================
set /p "CHOICE=Select an option (0-5): "
if "%CHOICE%"=="1" (
    %PYTHON_EXE% "%SCRIPT_DIR%run.py" eln
    goto :menu_end
)
if "%CHOICE%"=="2" (
    %PYTHON_EXE% "%SCRIPT_DIR%run.py" interactive-gel
    goto :menu_end
)
if "%CHOICE%"=="3" (
    %PYTHON_EXE% "%SCRIPT_DIR%run.py" interactive-plasmid
    goto :menu_end
)
if "%CHOICE%"=="4" (
    %PYTHON_EXE% "%SCRIPT_DIR%run.py" setup
    goto :menu_end
)
if "%CHOICE%"=="5" (
    %PYTHON_EXE% "%SCRIPT_DIR%run.py" --help
    goto :menu_end
)
if "%CHOICE%"=="0" exit /b 0

echo Invalid choice.
:menu_end
if not defined CI pause
exit /b 0
