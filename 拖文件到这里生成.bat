@echo off
rem ASCII only - see the web launcher bat for why.
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo.
  echo   [!] No file detected.
  echo.
  echo   Drag a CSV / TXT file onto this icon.
  echo   (Double-clicking it does nothing.)
  echo.
  pause
  exit /b 0
)
call "%~dp0_findpy.bat" || exit /b 1
if /i "%~x1"==".csv" (
  "%PY%" em.py build --in "%~1"
) else (
  "%PY%" em.py build --paste "%~1"
)
echo.
echo   [done] press any key to close.
pause
