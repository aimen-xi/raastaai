@echo off
rem RaastaAI demo server: double-click to start the API + public tunnel. Close the window to stop.
title RaastaAI server
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. See README: Run locally.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -u tools\serve_public.py
echo.
echo The server has stopped. Press any key to close this window.
pause >nul
