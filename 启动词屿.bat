@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
title Word Isle
if not exist "%~dp0runtime\python.exe" (
  echo Please extract the complete Windows ZIP before starting Word Isle.
  echo Missing: runtime\python.exe
  pause
  exit /b 1
)
set "WORDISLE_LOG_DIR=%LOCALAPPDATA%\WordIsleWeb"
if not defined LOCALAPPDATA set "WORDISLE_LOG_DIR=%USERPROFILE%\AppData\Local\WordIsleWeb"
if not exist "%WORDISLE_LOG_DIR%" mkdir "%WORDISLE_LOG_DIR%"
if not exist "%WORDISLE_LOG_DIR%" (
  echo Cannot create the Word Isle data folder.
  pause
  exit /b 1
)
set "PYTHONIOENCODING=utf-8"
echo Starting Word Isle. Please keep this window open.
echo Browser address: http://127.0.0.1:8765/
echo Startup log: "%WORDISLE_LOG_DIR%\startup.log"
"%~dp0runtime\python.exe" -X utf8 -B "%~dp0windows\start.py" >> "%WORDISLE_LOG_DIR%\startup.log" 2>&1
set "WORDISLE_EXIT=%ERRORLEVEL%"
if not "%WORDISLE_EXIT%"=="0" (
  echo.
  echo Word Isle stopped. Exit code: %WORDISLE_EXIT%
  echo Full error details: "%WORDISLE_LOG_DIR%\startup.log"
  start "" notepad.exe "%WORDISLE_LOG_DIR%\startup.log"
  pause
  exit /b %WORDISLE_EXIT%
)
