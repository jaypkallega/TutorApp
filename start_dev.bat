@echo off
title MathTutor — Development Mode
echo Starting development servers...
echo.

:: Start backend in new window
start "MathTutor Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait 2 seconds then start frontend
timeout /t 2 /nobreak > NUL

start "MathTutor Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo Both servers starting...
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173  (use this for development)
echo.
pause
