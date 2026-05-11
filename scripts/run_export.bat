@echo off
REM Entry point invoked by Windows Task Scheduler every 6 hours.
cd /d C:\Users\0200705\Downloads\dimpu
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
python -m src.main
exit /b %errorlevel%
