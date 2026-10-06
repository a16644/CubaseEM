@echo off
REM ---------------------------------------------------------------
REM  Push this repo to GitHub.
REM  !! ASCII ONLY !!  chcp 65001 + Chinese bytes in a .bat = cmd
REM  re-reads the file by byte offset and the Chinese lines become
REM  garbage commands (the classic "double click does nothing").
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo [X] git not found in PATH.
  pause
  exit /b 1
)

set /p GHUSER=GitHub username:
if "%GHUSER%"=="" (
  echo [X] no username given.
  pause
  exit /b 1
)

set /p GHREPO=Repo name [CubaseEM]:
if "%GHREPO%"=="" set GHREPO=CubaseEM

REM noreply address keeps your real email off the internet
git config user.name "%GHUSER%"
git config user.email "%GHUSER%@users.noreply.github.com"

REM rewrite the author of the very first commit only (safe: nothing else yet)
for /f %%i in ('git rev-list --count HEAD') do set NCOMMIT=%%i
if "%NCOMMIT%"=="1" git commit --amend --reset-author --no-edit >nul

git branch -M main
git remote remove origin >nul 2>&1
REM NOTE: use the ssh:// form on purpose. This machine has a global git rule
REM   url.https://github.com/.insteadof = git@github.com:
REM which rewrites git@github.com:USER/REPO.git into an https URL. The ssh://
REM form does not match that rule, so we keep real SSH (key auth, no password).
git remote add origin ssh://git@github.com/%GHUSER%/%GHREPO%.git

echo.
echo Checking SSH key ...
ssh -T -o BatchMode=yes -o ConnectTimeout=15 git@github.com 2>&1 | findstr /C:"successfully authenticated" >nul
if errorlevel 1 (
  echo [!] GitHub did not accept your SSH key yet.
  echo     Add the public key at https://github.com/settings/keys then run this again.
  echo     Public key file: %USERPROFILE%\.ssh\id_ed25519.pub
  pause
  exit /b 1
)

echo.
echo Pushing to ssh://git@github.com/%GHUSER%/%GHREPO%.git ...
git push -u origin main

if errorlevel 1 (
  echo.
  echo [X] push failed.
  echo   1. did you create the EMPTY repo on github.com/new ?
  echo   2. did you add your SSH public key in Settings ^> SSH and GPG keys ?
  echo   3. test it with:  ssh -T git@github.com
) else (
  echo.
  echo [OK] done -^> https://github.com/%GHUSER%/%GHREPO%
)
pause
