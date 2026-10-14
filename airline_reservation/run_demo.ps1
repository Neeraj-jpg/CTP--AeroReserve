$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
    & '.venv\Scripts\python.exe' -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& '.venv\Scripts\python.exe' -m uvicorn aerobooking.api:app --host 0.0.0.0 --port 8000
