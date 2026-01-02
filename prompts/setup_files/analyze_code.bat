@echo off
call "%~dp0config.bat"
cd ..

"%CLI_ANALYZER_PATH%\venv\Scripts\python.exe" "%CLI_ANALYZER_PATH%\main.py" --language %LANGUAGE% --path "." --verbosity minimal --output "code_analysis_results" --maxamountoferrors 50 --rules "code_analysis_rules.json"

cd %~dp0
pause
