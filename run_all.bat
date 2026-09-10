@echo off
echo ==============================================
echo   Starting ReelsMob Dashboard & Cloud Backend
echo ==============================================

:: Start Backend in the background
start "ReelsMob Backend (Port 8000)" cmd /c "if exist venv\Scripts\activate.bat (call venv\Scripts\activate.bat) & python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

:: Start Frontend in the background
start "ReelsMob Frontend (Port 9090)" cmd /c "cd frontend-react & npm run dev"

echo.
echo ✅ Servers are starting up!
echo.
echo  🖥️  Frontend UI: http://127.0.0.1:9090
echo  ⚙️  Backend API: http://127.0.0.1:8000
echo.
echo (Two command prompt windows just opened to run these servers. Keep them open!)
pause
