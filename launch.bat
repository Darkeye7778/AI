@echo off
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe assistant\main.py desktop
) else (
    python assistant\main.py desktop
)