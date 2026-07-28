@echo off
REM ===============================================================
REM  SkillSwap NSU  -  step 1 of 2
REM  Imports database\skillexchange_full.sql into the MySQL that
REM  ships with XAMPP. Start MySQL in the XAMPP Control Panel first.
REM ===============================================================
title SkillSwap NSU - import the database
cd /d "%~dp0"

echo.
echo   SkillSwap NSU  -  importing the database
echo   --------------------------------------------------
echo.

set "MYSQL=C:\xampp\mysql\bin\mysql.exe"
if not exist "%MYSQL%" set "MYSQL=D:\xampp\mysql\bin\mysql.exe"
if not exist "%MYSQL%" set "MYSQL=E:\xampp\mysql\bin\mysql.exe"

if not exist "%MYSQL%" (
  echo   Could not find mysql.exe inside XAMPP.
  echo   Looked in C:\xampp, D:\xampp and E:\xampp.
  echo.
  echo   If XAMPP lives somewhere else, edit this file and put the
  echo   correct path on the "set MYSQL=" line above.
  echo.
  pause
  exit /b 1
)

echo   Using: %MYSQL%
echo   Importing database\skillexchange_full.sql ...
echo.

"%MYSQL%" -u root < "database\skillexchange_full.sql"

if errorlevel 1 (
  echo.
  echo   Import FAILED.
  echo     * Is MySQL running?  Open the XAMPP Control Panel and press
  echo       Start next to MySQL, then run this file again.
  echo     * If your MySQL root user has a password, use:
  echo         "%MYSQL%" -u root -p ^< database\skillexchange_full.sql
  echo.
  pause
  exit /b 1
)

echo.
echo   Done. The skillexchange database now holds:
"%MYSQL%" -u root -e "USE skillexchange; SELECT 'users' AS table_name, COUNT(*) AS rows_ FROM users UNION ALL SELECT 'skills', COUNT(*) FROM skills UNION ALL SELECT 'userskills', COUNT(*) FROM userskills UNION ALL SELECT 'exchangerequests', COUNT(*) FROM exchangerequests UNION ALL SELECT 'sessions', COUNT(*) FROM sessions UNION ALL SELECT 'reviews', COUNT(*) FROM reviews;"

echo.
echo   Next: run 2-RUN-WEBSITE.bat
echo.
pause
