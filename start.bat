@echo off
echo Starting ReelGrab Backend on localhost...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)
python -m uvicorn backend.main:app --reload --port 8000
