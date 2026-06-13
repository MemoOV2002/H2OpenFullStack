@echo off
REM H2Open Quick Start Script for Windows
REM Starts both backend and frontend in separate command windows

echo.
echo Starting H2Open System...
echo.

REM Check if we're in the right directory
if not exist "backend\" (
    echo Error: Must run from h2open-project directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

if not exist "frontend\" (
    echo Error: Must run from h2open-project directory  
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Start backend in new window
echo Starting backend...
start "H2Open Backend" cmd /k "cd backend && venv\Scripts\activate && python main.py"

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start frontend in new window
echo Starting frontend...
start "H2Open Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo H2Open is starting!
echo.
echo URLs:
echo    Frontend: http://localhost:5173
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo Tip: Close the command windows to stop services
echo.
pause
