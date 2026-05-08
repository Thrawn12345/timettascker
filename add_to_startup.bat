@echo off
setlocal
set "KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"

if exist "%~dp0.env" (
    set "VBS=%~dp0start_hidden_cloud.vbs"
    echo  Using CLOUD mode (.env found)
) else (
    set "VBS=%~dp0start_hidden.vbs"
    echo  Using LOCAL mode (no .env)
)

echo Adding Time Tracker to startup...
reg add "%KEY%" /v "TimeTracker" /t REG_SZ /d "wscript.exe \"%VBS%\"" /f

if %errorlevel% == 0 (
    echo  [OK] Time Tracker will now start automatically at login.
    echo  To remove it, run remove_from_startup.bat
) else (
    echo  [FAIL] Could not add registry entry.
)
pause
