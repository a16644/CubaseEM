@echo off
rem ASCII only - see the web launcher bat for why.
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_findpy.bat" || exit /b 1

echo.
echo   1 = always on top    0 = cancel    Enter = show status
set /p C=choose [1/0/Enter]:
if "%C%"=="0" "%PY%" em\wintop.py off
if "%C%"=="1" "%PY%" em\wintop.py on
if "%C%"=="s" "%PY%" em\wintop.py status
if "%C%"=="" "%PY%" em\wintop.py status
echo.
pause
