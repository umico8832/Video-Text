@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_launcher.ps1"
if errorlevel 1 pause
