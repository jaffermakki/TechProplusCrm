@echo off
REM Stops the Tech-Pro+ CRM server. Use this before updating the app's files,
REM or any time you need to restart it manually.
REM Note: if you set up the auto-restart Task Scheduler task, the app will
REM relaunch on next reboot - this only stops the currently running process.

echo Stopping Tech-Pro+ CRM...
taskkill /F /FI "WINDOWTITLE eq Tech-Pro+ CRM*" /T >nul 2>&1
taskkill /F /IM python.exe /FI "MODULES eq waitress*" >nul 2>&1

REM Fallback: kill any python.exe running run_production.py for this app
wmic process where "CommandLine like '%%run_production.py%%'" call terminate >nul 2>&1

echo Done. The app is stopped.
pause
