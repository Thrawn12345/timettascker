@echo off
title Time Tracker (Cloud)
cd /d "%~dp0"

:: Load DATABASE_URL from .env
for /f "usebackq tokens=1,* delims==" %%A in (".env") do set %%A=%%B

if "%DATABASE_URL%"=="" (
    echo  [ERROR] .env file missing or DATABASE_URL not set.
    pause
    exit /b 1
)

echo  [Cloud mode] Sending data to Neon PostgreSQL
python backend\main.py
pause
