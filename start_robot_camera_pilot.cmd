@echo off
setlocal
cd /d "%~dp0"
echo Starting the no-motion robot-camera pilot. Keep this window open.
echo Stop the commissioning server first. Do not start any robot applications.
".venv\Scripts\python.exe" "scripts\run_robot_camera_pilot.py" --robot-ip 192.168.1.251
set "pilot_exit=%ERRORLEVEL%"
echo Pilot server stopped with exit code %pilot_exit%.
pause
exit /b %pilot_exit%
