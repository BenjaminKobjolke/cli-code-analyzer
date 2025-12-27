@echo off
REM Analyze Python code using cli-code-analyzer

cd /d "%~dp0..\.."
call venv\Scripts\python.exe main.py --language python --path "%~dp0src" --verbosity minimal --rules "%~dp0rules.json"
pause
