@echo off
cd /d "%~dp0..\.."

call venv\Scripts\python.exe php_fixer.py --path "%~dp0src" --rules "%~dp0rules.json"

cd /d "%~dp0"
