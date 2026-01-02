@echo off
call "%~dp0config.bat"
cd ..

if "%LANGUAGE%"=="python" (
    "%CLI_ANALYZER_PATH%\venv\Scripts\python.exe" "%CLI_ANALYZER_PATH%\ruff_fixer.py" --path "." --rules "code_analysis_rules.json"
) else if "%LANGUAGE%"=="php" (
    "%CLI_ANALYZER_PATH%\venv\Scripts\python.exe" "%CLI_ANALYZER_PATH%\php_fixer.py" --path "." --rules "code_analysis_rules.json"
) else (
    echo No fixer available for language: %LANGUAGE%
)

cd %~dp0
pause
