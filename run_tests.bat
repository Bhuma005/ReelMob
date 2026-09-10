@echo off
echo ===================================================
echo   ReelsMob Backend Test Suite Runner
echo ===================================================
python -m pytest backend/tests/ -v
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Test suite failed with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
echo [SUCCESS] All backend reliability tests passed!
