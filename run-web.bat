@echo off
chcp 65001 >nul
cd /d "%~dp0"
call scripts\run-web.bat %*
