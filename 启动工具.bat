@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_findpy.bat" || exit /b 1
"%PY%" em.py menu
pause
