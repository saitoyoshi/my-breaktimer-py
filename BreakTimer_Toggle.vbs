' BreakTimer Ultra - Toggle Launcher (hidden window)
' This VBS wrapper runs the PowerShell toggle script without showing a console window.
Set objShell = CreateObject("WScript.Shell")
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strDir
objShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & strDir & "\toggle_breaktimer.ps1""", 0, False
