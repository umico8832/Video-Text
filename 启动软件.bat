@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 launcher.py
    if %errorlevel%==0 goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python launcher.py
    goto :eof
)

echo Python was not found. Please install Python 3.12 and enable PATH.
pause
