@echo off
REM ===============================================================
REM  SkillSwap NSU  -  step 2 of 2
REM  Installs the three Python packages (first run only) and starts
REM  the Flask server on http://127.0.0.1:5000
REM ===============================================================
title SkillSwap NSU - web server
cd /d "%~dp0"

echo.
echo   SkillSwap NSU  -  starting the web server
echo   --------------------------------------------------
echo.

REM ---- find Python ------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"

if not defined PY (
  echo   Python is not installed, or it is not on your PATH.
  echo.
  echo   Install it from https://www.python.org/downloads/
  echo   and tick "Add python.exe to PATH" on the first screen.
  echo.
  pause
  exit /b 1
)

echo   Python : %PY%
echo   Checking the required packages ...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo   Could not install the packages. Check your internet connection.
  echo.
  pause
  exit /b 1
)

echo   Opening http://127.0.0.1:5000 in your browser ...
start "" http://127.0.0.1:5000

echo.
%PY% app.py

echo.
echo   The server has stopped.
pause
