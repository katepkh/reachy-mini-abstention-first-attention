@echo off
setlocal
cd /d "%~dp0"
echo Starting the separate playback diagnostic. Keep this window open.
echo Stop the pilot/commissioning servers and close their browser tabs first.
echo No pilot trial will be recorded or advanced. No movement or response.
".venv\Scripts\python.exe" "scripts\run_robot_camera_diagnostic.py" --robot-ip 192.168.1.251
set "diagnostic_exit=%ERRORLEVEL%"
echo Diagnostic server stopped with exit code %diagnostic_exit%.
pause
exit /b %diagnostic_exit%
