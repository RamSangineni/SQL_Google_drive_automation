@echo off
REM Entry point invoked by Windows Task Scheduler every 6 hours.
REM Resolves project root from the script's own location so the file is portable.
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
python -m src.main
exit /b %errorlevel%
