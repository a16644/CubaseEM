@echo off
rem ASCII ONLY on purpose. Under "chcp 65001 + UTF-8-no-BOM bat", cmd re-reads
rem the file by byte offset after the code-page switch and mangles CJK lines,
rem then executes them (classic: 'XXecho' is not recognized). chcp 65001 is
rem needed so Python can print Chinese, so the bat itself must stay ASCII and
rem let Python do all the Chinese. See README "bat files" note.
chcp 65001 >nul
title Cubase Expression Map Editor
cd /d "%~dp0"
call "%~dp0_findpy.bat" || exit /b 1

echo.
echo   Cubase Expression Map Editor
echo   --------------------------------
echo.

"%PY%" em\app.py %*

echo.
echo   [stopped] press any key to close.
pause
