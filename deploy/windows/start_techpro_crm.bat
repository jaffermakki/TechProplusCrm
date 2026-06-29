@echo off
REM Tech-Pro+ CRM - Windows launcher
REM Activates the virtual environment and starts the production server.
REM If the server crashes for any reason, this loop restarts it automatically
REM after a short pause, so the app comes back without anyone touching the computer.
REM
REM This file is what Task Scheduler runs on startup (via run_techpro_crm.vbs,
REM which hides this window so staff never see a black console box).

cd /d "%~dp0\..\.."

:restart_loop
call venv\Scripts\activate.bat
python run_production.py >> deploy\windows\techpro_crm.log 2>&1

REM If we get here, the server stopped or crashed. Wait 5 seconds and try again.
echo [%date% %time%] Server stopped or crashed - restarting in 5 seconds... >> deploy\windows\techpro_crm.log
timeout /t 5 /nobreak > nul
goto restart_loop
