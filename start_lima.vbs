Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\GIT"
Set env = WshShell.Environment("Process")
If env("LIMA_API_KEY") = "" And env("LIMA_CODE_API_KEY") = "" Then
  WScript.Echo "LIMA_API_KEY or LIMA_CODE_API_KEY environment variable is required."
  WScript.Quit 1
End If
If env("LIMA_API_KEY") = "" Then env("LIMA_API_KEY") = env("LIMA_CODE_API_KEY")
If env("LIMA_CODE_API_KEY") = "" Then env("LIMA_CODE_API_KEY") = env("LIMA_API_KEY")
env("LIMA_CODE_SERVER_URL") = "https://chat.donglicao.com"
WshShell.Run "cmd /c cd /d D:\GIT && ""C:\Program Files\Git\usr\bin\winpty.exe"" node D:\GIT\deepcode-cli\node_modules\tsx\dist\cli.mjs D:\GIT\deepcode-cli\src\cli.tsx", 1, False
