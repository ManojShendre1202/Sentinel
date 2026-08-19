@echo off
cd /d "%~dp0"

echo Starting Django (Waitress, port 8130)...
start "Sentinel - Django" cmd /k python server.py

echo Starting worker (extension WebSocket, port 8140)...
start "Sentinel - Worker" cmd /k python -m worker.main

echo Starting nginx (port 8100)...
start "Sentinel - Nginx" cmd /k "cd /d C:\nginx & nginx.exe -p "%~dp0nginx_run\" -c "%~dp0nginx.local.conf""

echo All three started in separate windows. Close this window or Ctrl+C each to stop.
