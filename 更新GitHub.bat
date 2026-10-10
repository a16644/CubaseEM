@echo off
REM ---------------------------------------------------------------
REM  One-click: commit everything and push to GitHub.
REM  !! ASCII ONLY !!  chcp 65001 + Chinese bytes inside a .bat makes
REM  cmd re-read the file by byte offset and the Chinese lines turn
REM  into garbage commands (the classic "double click does nothing").
REM  So every message below is English on purpose.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo [X] git not found in PATH.
  pause
  exit /b 1
)

echo ===============================================================
echo  CubaseEM  ->  GitHub
echo ===============================================================
echo.
echo [1/4] What changed:
echo ---------------------------------------------------------------
git status --short
echo ---------------------------------------------------------------
echo.

git diff --quiet HEAD 2>nul
if not errorlevel 1 (
  if "%~1"=="" (
    echo Nothing changed since the last commit.
    echo Press any key to close, or type a message if you still want a push.
    pause
    exit /b 0
  )
)

echo [2/4] Type a short note about this change.
echo       Leave it blank to abort ^(nothing is pushed^).
set NOTE=
set /p NOTE=Note: 
if "%NOTE%"=="" (
  if "%~1"=="" (
    echo Aborted. Nothing was committed or pushed.
    pause
    exit /b 0
  )
  set NOTE=%~1
)

echo.
echo [3/4] Staging and committing...
git add -A
if errorlevel 1 (
  echo [X] git add failed.
  pause
  exit /b 1
)
git commit -m "%NOTE%"
if errorlevel 1 (
  echo [X] git commit failed - maybe nothing was staged.
  pause
  exit /b 1
)

echo.
echo [4/4] Pushing to GitHub...
git push origin main
if errorlevel 1 (
  echo.
  echo [X] Push failed. Common causes:
  echo   - another copy of the repo already pushed new commits
  echo     -^> run:  git pull --rebase origin main   then try again
  echo   - SSH key not loaded / network down
  pause
  exit /b 1
)

echo.
echo ===============================================================
echo  Done.  https://github.com/a16644/CubaseEM/tree/main
echo ===============================================================
echo.
git log --oneline -3
echo.
pause
