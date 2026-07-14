@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment missing. Run: py -3.11 -m venv .venv
    exit /b 1
)
call .venv\Scripts\activate.bat
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
