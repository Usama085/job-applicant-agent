@echo off
REM ============================================
REM AI Job Application Agent - Daily Launcher
REM ============================================

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d "%PROJECT_ROOT%"

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python -m job_agent.main
set EXIT_CODE=%ERRORLEVEL%

if defined VIRTUAL_ENV (
    deactivate
)

exit /b %EXIT_CODE%
