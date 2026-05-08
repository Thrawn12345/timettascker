@echo off
setlocal

set "VBS=%~dp0start_hidden.vbs"
set "KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"

echo Adding Time Tracker to startup...

reg add "%KEY%" /v "TimeTracker" /t REG_SZ /d "wscript.exe \"%VBS%\"" /f

if %errorlevel% == 0 (
    echo.
    echo  [OK] Time Tracker will now start automatically at login.
    echo  To remove it, run remove_from_startup.bat
) else (
    echo  [FAIL] Could not add registry entry.
)

pause
