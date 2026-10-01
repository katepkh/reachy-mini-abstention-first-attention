@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe was not found in this project.
  echo Recreate the project environment before running commissioning.
  pause
  exit /b 1
)

echo Starting the receive-only Reachy camera commissioning tool...
echo Keep this window open until the CSV and metadata JSON are downloaded.
echo No movement or response authority is enabled.
echo.

".venv\Scripts\python.exe" "scripts\run_robot_camera_commissioning.py" --robot-ip 192.168.1.251
set "commissioning_exit=%ERRORLEVEL%"

echo.
if not "%commissioning_exit%"=="0" (
  echo The commissioning server stopped with exit code %commissioning_exit%.
) else (
  echo The commissioning server has stopped.
)
echo You may close this window after reading the message above.
pause
exit /b %commissioning_exit%
