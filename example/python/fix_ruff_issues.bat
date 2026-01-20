@echo off
REM Auto-fix Python issues using Ruff with settings from rules.json

cd /d "%~dp0..\.."
call venv\Scripts\python.exe ruff_fixer.py --path "%~dp0src" --rules "%~dp0rules.json"

