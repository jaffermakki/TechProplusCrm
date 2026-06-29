' Tech-Pro+ CRM - silent launcher
' Runs start_techpro_crm.bat with the console window hidden, so staff never see
' a black command-prompt box on the shop computer's desktop. This is the file
' Task Scheduler should point at.

Set objShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run """" & strPath & "\start_techpro_crm.bat""", 0, False
