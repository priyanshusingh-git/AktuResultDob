@echo off
title AKTU Result
color 0b
set "AKTUBOT_HTTP_HOME=%~dp0.aktubot_http_home"

echo ===========================================
echo  Starting AKTU Result
echo ===========================================
echo.
echo Checking dependencies...
echo Using local app home: %AKTUBOT_HTTP_HOME%

where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: Python was not found on this computer.
        echo Please download and install Python from: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

%PY_CMD% -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo.
echo Starting application window...
%PY_CMD% main.py

echo.
echo AKTU Result has shut down.
pause
