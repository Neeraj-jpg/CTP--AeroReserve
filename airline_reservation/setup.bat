@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1
echo Setup complete. Run run_demo.bat and open http://localhost:8000
endlocal
