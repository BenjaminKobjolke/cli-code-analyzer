@echo off
if not exist "%~dp0analyze_code_config.bat" (
    echo ERROR: analyze_code_config.bat not found.
    echo Copy analyze_code_config.example.bat to analyze_code_config.bat and set your CLI_ANALYZER_PATH and LANGUAGE.
    exit /b 1
)
call "%~dp0analyze_code_config.bat"
cd /d "%~dp0.."

if "%LANGUAGE%"=="python" (
    "%CLI_ANALYZER_PATH%\venv\Scripts\python.exe" "%CLI_ANALYZER_PATH%\ruff_fixer.py" --path "." --rules "code_analysis_rules.json"
) else if "%LANGUAGE%"=="php" (
    "%CLI_ANALYZER_PATH%\venv\Scripts\python.exe" "%CLI_ANALYZER_PATH%\php_fixer.py" --path "." --rules "code_analysis_rules.json"
) else (
    echo No fixer available for language: %LANGUAGE%
)

cd /d "%~dp0"
