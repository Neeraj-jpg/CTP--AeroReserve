@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup.bat
call ".venv\Scripts\activate.bat"
python -m uvicorn aerobooking.api:app --host 0.0.0.0 --port 8000
endlocal
