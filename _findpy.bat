@echo off
rem Find a usable Python: _runtime\pythonw.exe (bundled) first, then PATH,
rem then a common install path. Never fail silently - say what happened.
rem ASCII only, same reason as the web launcher bat (see README).
set "PY="
if exist "%~dp0_runtime\pythonw.exe" set "PY=%~dp0_runtime\pythonw.exe"
if not defined PY if exist "%~dp0_runtime\python.exe" set "PY=%~dp0_runtime\python.exe"
if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY (
  echo.
  echo   [X] Python not found.
  echo.
  echo   You do NOT need Python to use this tool:
  echo   just double-click the .exe in the dist folder.
  echo.
  echo   To run from source instead, install Python 3.9+
  echo   and re-check "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)
rem Never add endlocal here - it would wipe PY for the caller.
exit /b 0
