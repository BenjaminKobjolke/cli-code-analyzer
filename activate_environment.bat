@echo off
call %~dp0\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Virtual environment activation failed.
    exit /b 1
)
echo Virtual environment activated.
python --version
for /f "tokens=1,2" %%a in ('pip --version') do echo %%a %%b
