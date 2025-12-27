@echo off
call venv\Scripts\python.exe main.py --language python --path "." --verbosity minimal --output "code_analysis_results" --maxamountoferrors 50 --rules "code_analysis_rules.json"
pause
