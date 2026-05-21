@echo off
title MathTutor — Local Math Learning App
color 0A
echo =========================================
echo   MathTutor v1.0 — Starting...
echo =========================================
echo.

cd /d "%~dp0"

:: Activate virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Please run:  python -m venv venv
    pause
    exit /b 1
)

call venv\Scripts\activate

:: Check dependencies
python -c "import fastapi, uvicorn" 2>NUL
if %errorlevel% neq 0 (
    echo Installing Python dependencies...
    pip install -r requirements.txt
)

:: Get local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address" /c:"IPv4"') do (
    set LOCAL_IP=%%a
    goto :found
)
:found
set LOCAL_IP=%LOCAL_IP: =%

echo.
echo =========================================
echo   Server running!
echo.
echo   This computer:  http://localhost:8000
echo   iPad / tablet:  http://%LOCAL_IP%:8000
echo   API docs:       http://localhost:8000/docs
echo.
echo   Keep this window open.
echo   Press Ctrl+C to stop.
echo =========================================
echo.

:: If frontend has been built, serve it from FastAPI
:: Otherwise the dev server must be run separately: cd frontend && npm run dev
if not exist "frontend\dist" (
    echo NOTE: Frontend not built. Run these in a separate window:
    echo   cd frontend
    echo   npm install
    echo   npm run dev
    echo   Then open http://localhost:5173
    echo.
)

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
