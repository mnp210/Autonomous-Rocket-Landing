@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\play_demo.py %*
) else (
    python scripts\play_demo.py %*
)
