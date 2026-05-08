@echo off
echo Opening port 7878 for Time Tracker (LAN access)...

netsh advfirewall firewall add rule ^
  name="Time Tracker" ^
  dir=in ^
  action=allow ^
  protocol=TCP ^
  localport=7878

if %errorlevel% == 0 (
    echo  [OK] Firewall rule added. Phone can now reach the dashboard.
) else (
    echo  [FAIL] Run this script as Administrator.
)
pause
