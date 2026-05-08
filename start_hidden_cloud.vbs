Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c """ & Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\")) & "start_cloud.bat""", 0, False
