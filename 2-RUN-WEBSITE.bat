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

REM ---- find Python -------------------------------------------------
REM  Each candidate is actually RUN, not just looked up on the PATH.
REM  Windows ships a fake python.exe that only opens the Microsoft Store,
REM  and "where python" happily finds that one - running it does not work.
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  python3 -c "import sys" >nul 2>&1 && set "PY=python3"
)

if not defined PY (
  echo   Python is not installed on this computer.
  echo.
  echo   Windows has a placeholder "python" that only opens the Microsoft
  echo   Store, which is why you may see "Python was not found".
  echo.
  echo   Install the real thing:
  echo     https://www.python.org/downloads/
  echo   On the FIRST installer screen, tick "Add python.exe to PATH",
  echo   then press "Install Now". Close this window and run this file
  echo   again afterwards.
  echo.
  echo   You do NOT need Python for the GitHub Pages version of the site -
  echo   only for this full Flask build that talks to MySQL.
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
