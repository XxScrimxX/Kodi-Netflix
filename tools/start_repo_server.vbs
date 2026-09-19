' Starts tools\repo_server.py with python.exe in a hidden window.
' Run at login by the "Unknown Kodi Repository" scheduled task. python.exe (not pythonw.exe) is used
' because Windows Firewall already allows it to accept connections from the Fire TV Stick.
Set fso = CreateObject("Scripting.FileSystemObject")
toolsDir = fso.GetParentFolderName(WScript.ScriptFullName)
python = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python314\python.exe")
CreateObject("WScript.Shell").Run """" & python & """ """ & toolsDir & "\repo_server.py""", 0, False
