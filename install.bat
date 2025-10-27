@echo off
echo Creating virtual environment...
call python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing requirements...
call pip install -r requirements.txt

echo Installation complete!

