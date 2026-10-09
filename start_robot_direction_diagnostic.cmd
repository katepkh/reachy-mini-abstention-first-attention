@echo off
setlocal
cd /d "%~dp0"
echo Starting the separate three-position direction diagnostic.
echo Stop old pilot/diagnostic servers and close their browser tabs first.
echo Keep this window open. No robot movement, response or pilot acceptance.
".venv\Scripts\python.exe" "scripts\run_robot_direction_diagnostic.py" --robot-ip 192.168.1.251
set "direction_exit=%ERRORLEVEL%"
echo Direction diagnostic stopped with exit code %direction_exit%.
pause
exit /b %direction_exit%
