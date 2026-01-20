@echo off
cd /d "%~dp0..\.."

call venv\Scripts\python.exe main.py --language php --path "%~dp0src" --verbosity minimal --output "%~dp0code_analysis_results" --maxamountoferrors 50 --rules "%~dp0rules.json"

cd /d "%~dp0"

