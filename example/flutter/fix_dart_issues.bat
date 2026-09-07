@echo off
REM Auto-fix Dart lint issues using dart fix --apply

cd /d "%~dp0..\.."
call venv\Scripts\python.exe dart_fixer.py --path "%~dp0lib" --rules "%~dp0rules.json"
