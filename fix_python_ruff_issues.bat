@echo off
call venv\Scripts\python.exe ruff_fixer.py --path "." --rules "code_analysis_rules.json"
pause
