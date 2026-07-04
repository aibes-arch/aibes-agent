@echo off
chcp 65001 >nul
cd /d "%~dp0.."
powershell -ExecutionPolicy ByPass -File "scripts\run.ps1" %*
pause
