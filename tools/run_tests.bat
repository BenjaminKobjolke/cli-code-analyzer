@echo off
setlocal
set ROOT=%~dp0..
call "%ROOT%\venv\Scripts\activate.bat"
pushd "%ROOT%"
pytest tests\unit -v
set RC=%ERRORLEVEL%
popd
exit /b %RC%
