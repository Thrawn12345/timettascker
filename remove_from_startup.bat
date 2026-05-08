@echo off
set "KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"

reg delete "%KEY%" /v "TimeTracker" /f >nul 2>&1

if %errorlevel% == 0 (
    echo  [OK] Time Tracker removed from startup.
) else (
    echo  [--] No startup entry found.
)

pause
